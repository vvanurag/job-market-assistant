"""Run every metric's real SQL against a tiny Gold schema in DuckDB."""

from datetime import date

import duckdb
import pytest

from jobmarket.api.metrics import MetricRequest, run_metric
from jobmarket.settings import Settings

JOBS = [
    # key, title, city, work_mode, seniority, posted, status, company, skills
    (
        "a",
        "Senior Data Engineer",
        "Hyderabad",
        "hybrid",
        "senior",
        date(2026, 10, 5),
        "open",
        "Acme",
        ["Python", "dbt"],
    ),
    ("b", "Data Engineer", "Bengaluru", "remote", "mid", date(2026, 10, 12), "open", "Acme", ["Python", "Databricks"]),
    ("c", "Analytics Engineer", "Bengaluru", "hybrid", "mid", date(2026, 10, 13), "closed", "Beta", ["dbt", "SQL"]),
    ("d", "ML Engineer", "Hyderabad", "on-site", "lead", date(2026, 9, 1), "open", "Gamma", ["Python", "Databricks"]),
]


@pytest.fixture
def settings(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create schema gold")
    con.execute("create table gold.dim_company (company_key varchar, company_name varchar)")
    con.execute("create table gold.dim_location (location_key varchar, city varchar)")
    con.execute("create table gold.dim_skill (skill_key varchar, skill_name varchar, category varchar)")
    con.execute(
        "create table gold.fct_postings (posting_key varchar, title varchar, company_key varchar, location_key varchar,"
        " work_mode varchar, seniority varchar, posted_date date, status varchar, url varchar)"
    )
    con.execute("create table gold.fct_posting_skills (posting_key varchar, skill_key varchar)")
    for company in {j[7] for j in JOBS}:
        con.execute("insert into gold.dim_company values (?, ?)", [company.lower(), company])
    for city in ("Hyderabad", "Bengaluru"):
        con.execute("insert into gold.dim_location values (?, ?)", [city.lower(), city])
    for skill in {s for j in JOBS for s in j[8]}:
        con.execute("insert into gold.dim_skill values (?, ?, 'x')", [skill.lower(), skill])
    for key, title, city, mode, level, posted, status, company, skills in JOBS:
        con.execute(
            "insert into gold.fct_postings values (?, ?, ?, ?, ?, ?, ?, ?, null)",
            [key, title, company.lower(), city.lower(), mode, level, posted, status],
        )
        for s in skills:
            con.execute("insert into gold.fct_posting_skills values (?, ?)", [key, s.lower()])
    con.close()
    return Settings(_env_file=None, duckdb_path=path)


def run(settings, **kw):
    return run_metric(settings, MetricRequest(**kw), today=date(2026, 10, 20))


def test_top_skills_ranks_and_reports_scope(settings):
    r = run(settings, metric="top_skills", limit=2)
    assert r.rows[0] == ["Python", "x", 3, 75.0]
    assert r.jobs_counted == 4 and r.date_from == date(2026, 9, 1) and r.date_to == date(2026, 10, 13)
    assert "Filters: all jobs" in r.summary and "Posted dates 2026-09-01 to 2026-10-13" in r.summary


def test_compare_cities_for_a_skill_uses_each_citys_share(settings):
    r = run(settings, metric="compare_cities", skill="Databricks")
    assert sorted(r.rows) == [["Bengaluru", 1, 50.0], ["Hyderabad", 1, 50.0]]


def test_filters_combine(settings):
    r = run(settings, metric="count_jobs", filters={"cities": ["Bengaluru"], "open_only": True})
    assert r.rows == [[1]] and "open jobs only" in r.filters_applied


def test_role_keywords_skills_and_recency(settings):
    r = run(settings, metric="count_jobs", filters={"role_keywords": ["data engineer"], "skills_all": ["dbt"]})
    assert r.rows == [[1]]
    r = run(settings, metric="count_jobs", filters={"posted_within_days": 10})
    assert r.jobs_counted == 2


def test_grouping_and_trend(settings):
    r = run(settings, metric="count_jobs", group_by="seniority")
    assert r.rows[0] == ["mid", 2]
    r = run(settings, metric="skill_trend", skill="Python", grain="month")
    assert [row[1] for row in r.rows] == [1, 2]


def test_top_companies(settings):
    assert run(settings, metric="top_companies").rows[0] == ["Acme", 2]


def test_skill_trend_needs_a_skill(settings):
    with pytest.raises(ValueError):
        run(settings, metric="skill_trend")
