"""The analytics layer: pre-defined metrics over Gold (FR-QA-02, NFR-13, ADR-0008).

The language model never writes SQL. It chooses one metric by name and fills in typed
parameters; this module validates them and runs fixed, parameterised, read-only SQL
against Gold. A hostile question can at worst choose the wrong metric. It can't
change what SQL runs, write data, or read anything outside Gold.

Every result states the filters, the date range and the number of jobs counted
(FR-QA-04).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from jobmarket.settings import Settings
from jobmarket.warehouse import read_gold

City = Literal["Hyderabad", "Bengaluru", "Remote (India)"]
WorkMode = Literal["remote", "hybrid", "on-site"]
Seniority = Literal["intern", "junior", "mid", "senior", "lead", "manager"]


class MetricFilters(BaseModel):
    """Filters every metric accepts. Empty means "all"."""

    cities: list[City] = Field(default_factory=list)
    work_modes: list[WorkMode] = Field(default_factory=list)
    seniorities: list[Seniority] = Field(default_factory=list)
    role_keywords: list[str] = Field(
        default_factory=list, description="Words the job title must contain, any of them, e.g. ['analytics engineer']"
    )
    company: str | None = Field(None, description="Company name or part of it")
    skills_all: list[str] = Field(default_factory=list, description="Skill names every job must mention")
    posted_within_days: int | None = Field(None, ge=1, le=3650)
    open_only: bool = False

    @field_validator("role_keywords", "skills_all")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        return [v.strip()[:60] for v in values if v.strip()][:10]


class MetricRequest(BaseModel):
    metric: Literal["top_skills", "skill_trend", "compare_cities", "count_jobs", "top_companies"]
    filters: MetricFilters = Field(default_factory=MetricFilters)
    skill: str | None = Field(None, description="For skill_trend and compare_cities: the skill to measure")
    group_by: Literal["none", "city", "work_mode", "seniority", "week", "month"] = "none"
    grain: Literal["week", "month"] = "week"
    limit: int = Field(10, ge=1, le=50)


class MetricResult(BaseModel):
    metric: str
    columns: list[str]
    rows: list[list]
    jobs_counted: int
    date_from: date | None
    date_to: date | None
    filters_applied: list[str]
    summary: str


METRIC_DESCRIPTIONS = {
    "top_skills": "Most frequently requested skills, ranked, with job counts and share of jobs.",
    "skill_trend": "Jobs mentioning one skill per week or month (needs 'skill').",
    "compare_cities": "Jobs per city, optionally only those mentioning one skill ('skill'), with share of each city.",
    "count_jobs": "Number of jobs, optionally grouped by city, work_mode, seniority, week or month.",
    "top_companies": "Companies with the most jobs.",
}


def _job_filters(f: MetricFilters, settings_today: date) -> tuple[str, list, list[str]]:
    """SQL WHERE for the jobs CTE, its bound parameters, and a readable description."""
    clauses, params, described = ["1 = 1"], [], []
    if f.cities:
        clauses.append("l.city in (" + ", ".join("?" * len(f.cities)) + ")")
        params += f.cities
        described.append("city: " + ", ".join(f.cities))
    if f.work_modes:
        clauses.append("f.work_mode in (" + ", ".join("?" * len(f.work_modes)) + ")")
        params += f.work_modes
        described.append("work mode: " + ", ".join(f.work_modes))
    if f.seniorities:
        clauses.append("f.seniority in (" + ", ".join("?" * len(f.seniorities)) + ")")
        params += f.seniorities
        described.append("seniority: " + ", ".join(f.seniorities))
    if f.role_keywords:
        clauses.append("(" + " or ".join("lower(f.title) like ?" for _ in f.role_keywords) + ")")
        params += [f"%{k.lower()}%" for k in f.role_keywords]
        described.append("title contains: " + " or ".join(f.role_keywords))
    if f.company:
        clauses.append("lower(c.company_name) like ?")
        params.append(f"%{f.company.lower()}%")
        described.append(f"company: {f.company}")
    for skill in f.skills_all:
        clauses.append(
            "f.posting_key in (select ps.posting_key from gold.fct_posting_skills ps "
            "join gold.dim_skill s on s.skill_key = ps.skill_key where lower(s.skill_name) = ?)"
        )
        params.append(skill.lower())
    if f.skills_all:
        described.append("mentions: " + " and ".join(f.skills_all))
    if f.posted_within_days:
        clauses.append("f.posted_date >= ?")
        params.append(settings_today - timedelta(days=f.posted_within_days))
        described.append(f"posted in the last {f.posted_within_days} days")
    if f.open_only:
        clauses.append("f.status = 'open'")
        described.append("open jobs only")
    return " and ".join(clauses), params, described or ["all jobs"]


JOBS_CTE = """
with jobs as (
    select f.posting_key, f.title, f.work_mode, f.seniority, f.posted_date, f.status, f.url,
           c.company_name, l.city
    from gold.fct_postings f
    join gold.dim_company c on c.company_key = f.company_key
    join gold.dim_location l on l.location_key = f.location_key
    where {where}
)
"""


def run_metric(settings: Settings, request: MetricRequest, today: date | None = None) -> MetricResult:
    today = today or date.today()
    where, params, described = _job_filters(request.filters, today)
    cte = JOBS_CTE.format(where=where)

    totals = read_gold(
        settings, cte + "select count(*) as n, min(posted_date) as d0, max(posted_date) as d1 from jobs", params
    )[0]
    total, d0, d1 = int(totals["n"]), totals["d0"], totals["d1"]

    m, limit = request.metric, request.limit
    skill_params: list = []
    if m in ("skill_trend", "compare_cities") and request.skill:
        skill_join = (
            "join gold.fct_posting_skills ps on ps.posting_key = j.posting_key "
            "join gold.dim_skill s on s.skill_key = ps.skill_key and lower(s.skill_name) = ?"
        )
        skill_params = [request.skill.lower()]
    else:
        skill_join = ""
    if m == "skill_trend" and not request.skill:
        raise ValueError("skill_trend needs a skill")

    if m == "top_skills":
        sql = (
            cte + "select s.skill_name, s.category, count(*) as jobs from jobs j "
            "join gold.fct_posting_skills ps on ps.posting_key = j.posting_key "
            "join gold.dim_skill s on s.skill_key = ps.skill_key "
            f"group by s.skill_name, s.category order by jobs desc, s.skill_name limit {limit}"
        )
        rows = read_gold(settings, sql, params)
        columns = ["skill", "category", "jobs", "share_of_jobs"]
        data = [[r["skill_name"], r["category"], int(r["jobs"]), _share(r["jobs"], total)] for r in rows]
        lead = ", ".join(f"{r[0]} ({r[2]})" for r in data[:5])
        summary = f"Top skills across {total:,} jobs: {lead}."
    elif m == "skill_trend":
        period = "week" if request.grain == "week" else "month"
        sql = (
            cte + f"select date_trunc('{period}', j.posted_date) as period, count(*) as jobs from jobs j {skill_join} "
            "where j.posted_date is not null group by 1 order by 1"
        )
        rows = read_gold(settings, sql, params + skill_params)
        columns = [period, "jobs"]
        data = [[_as_date(r["period"]), int(r["jobs"])] for r in rows]
        with_skill = sum(r[1] for r in data)
        summary = f"{with_skill:,} of {total:,} jobs mention {request.skill}, across {len(data)} {period}s." + (
            f" Busiest {period}: {max(data, key=lambda r: r[1])[0]}." if data else ""
        )
    elif m == "compare_cities":
        sql = cte + f"select j.city, count(*) as jobs from jobs j {skill_join} group by j.city order by jobs desc"
        rows = read_gold(settings, sql, params + skill_params)
        city_totals = {
            r["city"]: int(r["n"])
            for r in read_gold(settings, cte + "select city, count(*) as n from jobs group by city", params)
        }
        columns = ["city", "jobs", "share_of_city_jobs"]
        data = [[r["city"], int(r["jobs"]), _share(r["jobs"], city_totals.get(r["city"], 0))] for r in rows]
        what = f"jobs mentioning {request.skill}" if request.skill else "jobs"
        summary = "; ".join(f"{c}: {n:,} {what} ({s}% of its jobs)" for c, n, s in data) + "."
    elif m == "count_jobs":
        group = request.group_by
        if group == "none":
            columns, data = ["jobs"], [[total]]
            summary = f"{total:,} jobs match."
        else:
            expr = {
                "city": "j.city",
                "work_mode": "j.work_mode",
                "seniority": "j.seniority",
                "week": "date_trunc('week', j.posted_date)",
                "month": "date_trunc('month', j.posted_date)",
            }[group]
            sql = (
                cte
                + f"select {expr} as grp, count(*) as jobs from jobs j group by 1 order by "
                + ("1" if group in ("week", "month") else "jobs desc")
            )
            rows = read_gold(settings, sql, params)
            columns = [group, "jobs"]
            data = [[_as_date(r["grp"]) if group in ("week", "month") else r["grp"], int(r["jobs"])] for r in rows]
            summary = (
                f"{total:,} jobs, by {group.replace('_', ' ')}: " + ", ".join(f"{g}: {n:,}" for g, n in data[:8]) + "."
            )
    else:  # top_companies
        sql = (
            cte + f"select j.company_name, count(*) as jobs from jobs j group by 1 order by jobs desc, 1 limit {limit}"
        )
        rows = read_gold(settings, sql, params)
        columns = ["company", "jobs"]
        data = [[r["company_name"], int(r["jobs"])] for r in rows]
        summary = f"Companies with the most jobs (of {total:,}): " + ", ".join(f"{c} ({n})" for c, n in data[:5]) + "."

    scope = f" Filters: {'; '.join(described)}."
    dates = f" Posted dates {_as_date(d0)} to {_as_date(d1)}." if d0 else ""
    return MetricResult(
        metric=m,
        columns=columns,
        rows=data,
        jobs_counted=total,
        date_from=_as_date(d0),
        date_to=_as_date(d1),
        filters_applied=described,
        summary=summary + scope + dates,
    )


def _share(part, whole) -> float:
    return round(100 * int(part) / int(whole), 1) if whole else 0.0


def _as_date(value):
    if value is None:
        return None
    return value.date() if hasattr(value, "date") and callable(value.date) else value
