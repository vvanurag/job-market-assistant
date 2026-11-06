"""Resume matching and skill-gap analysis (FR-QA-06, US-08, US-09, Q5 option C).

The resume is read in memory and never stored or logged (NFR-10). Skills are found
locally with the skill dictionary; from then on only the skill list is used. Matching
is deterministic, so each match comes with an exact reason ("has 7 of the job's 9
skills"), not a generated one.
"""

from __future__ import annotations

import io
from collections import Counter
from dataclasses import dataclass
from datetime import date

from jobmarket.api.metrics import JOBS_CTE, MetricFilters, _job_filters
from jobmarket.settings import Settings
from jobmarket.skills import extract_skills
from jobmarket.warehouse import read_gold

MIN_JOB_SKILLS = 3  # jobs listing fewer skills would match "100%" too easily


def resume_text(content: bytes, filename: str | None) -> str:
    """Plain text from an uploaded PDF or text file."""
    if (filename or "").lower().endswith(".pdf") or content[:4] == b"%PDF":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    return content.decode("utf-8", errors="replace")


@dataclass
class JobMatch:
    posting_key: str
    title: str
    company_name: str
    city: str
    url: str | None
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    reason: str


@dataclass
class SkillGap:
    skill: str
    jobs: int
    share_of_jobs: float


@dataclass
class MatchResult:
    resume_skills: list[str]
    matches: list[JobMatch]
    gaps: list[SkillGap]
    jobs_considered: int
    filters_applied: list[str]


def match_resume(settings: Settings, text: str, filters: MetricFilters, limit: int = 10) -> MatchResult:
    have = sorted({s.name for s in extract_skills(text)})
    filters = filters.model_copy(update={"open_only": True})
    where, params, described = _job_filters(filters, date.today())
    rows = read_gold(
        settings,
        JOBS_CTE.format(where=where)
        + """
        select j.posting_key, j.title, j.company_name, j.city, j.url, s.skill_name
        from jobs j
        join gold.fct_posting_skills ps on ps.posting_key = j.posting_key
        join gold.dim_skill s on s.skill_key = ps.skill_key
        """,
        params,
    )
    jobs: dict[str, dict] = {}
    for r in rows:
        job = jobs.setdefault(r["posting_key"], {**r, "skills": set()})
        job["skills"].add(r["skill_name"])

    have_set = set(have)
    matches = []
    for key, job in jobs.items():
        wanted = job["skills"]
        if len(wanted) < MIN_JOB_SKILLS:
            continue
        matched = sorted(wanted & have_set)
        missing = sorted(wanted - have_set)
        score = len(matched) / len(wanted)
        reason = f"Has {len(matched)} of the {len(wanted)} skills this job mentions"
        reason += f"; missing: {', '.join(missing[:5])}" + ("…" if len(missing) > 5 else "") if missing else "."
        matches.append(
            JobMatch(
                key,
                job["title"],
                job["company_name"],
                job["city"],
                job["url"],
                round(score, 3),
                matched,
                missing,
                reason,
            )
        )
    matches.sort(key=lambda m: (-m.score, -len(m.matched_skills), m.title))

    demand = Counter(skill for job in jobs.values() for skill in job["skills"])
    gaps = [
        SkillGap(skill, n, round(100 * n / len(jobs), 1)) for skill, n in demand.most_common() if skill not in have_set
    ][:10]
    return MatchResult(have, matches[:limit], gaps, len(jobs), described)
