"""Compare Silver and Gold between DuckDB and Snowflake (NFR-24, ADR-0005).

For each table, the columns that carry its meaning (keys, classifications, counts) are
read from both engines, normalised to text, and compared as multisets of rows. Equal
results mean the same dbt models produced the same data on both engines.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

# table -> columns compared. Free text is left out: it's derived from the same Bronze
# bytes, and the fingerprint and classification columns depend on it.
COMPARISONS: dict[str, list[str]] = {
    "silver.slv_postings": [
        "posting_key",
        "city",
        "city_match_level",
        "is_canonical",
        "is_target_role",
        "content_fingerprint",
        "canonical_posting_key",
        "posted_date",
    ],
    "silver.slv_posting_skills": ["posting_key", "skill_id"],
    "silver.slv_posting_attributes": [
        "posting_key",
        "seniority",
        "seniority_basis",
        "min_years_experience",
        "experience_phrase",
        "work_mode",
        "work_mode_basis",
    ],
    "gold.fct_postings": [
        "posting_key",
        "company_key",
        "location_key",
        "posted_date_key",
        "repost_count",
        "skill_count",
        "seniority",
        "work_mode",
    ],
    "gold.fct_posting_skills": ["posting_key", "skill_key", "company_key", "location_key", "posted_date_key"],
    "gold.dim_company": ["company_key", "normalized_name", "spelling_variants"],
    "gold.dim_skill": ["skill_key", "skill_name", "category"],
    "gold.dim_location": ["location_key", "city", "state"],
    "gold.dim_date": ["date_key", "date_day", "day_of_week", "week_start", "is_weekend"],
}


@dataclass
class TableComparison:
    table: str
    rows_a: int
    rows_b: int
    only_in_a: int
    only_in_b: int
    examples: list[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return self.only_in_a == 0 and self.only_in_b == 0


def normalise(value) -> str:
    """Render a value the same way whichever engine returned it."""
    if value is None:
        return "∅"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal | float) and float(value).is_integer():
        return str(int(value))
    return str(value)


def compare_rows(table: str, rows_a: list[tuple], rows_b: list[tuple], max_examples: int = 3) -> TableComparison:
    a = Counter(tuple(normalise(v) for v in row) for row in rows_a)
    b = Counter(tuple(normalise(v) for v in row) for row in rows_b)
    only_a, only_b = a - b, b - a
    examples = [f"only in A: {r}" for r in list(only_a)[:max_examples]]
    examples += [f"only in B: {r}" for r in list(only_b)[:max_examples]]
    return TableComparison(table, len(rows_a), len(rows_b), sum(only_a.values()), sum(only_b.values()), examples)


def compare(duckdb_con, snowflake_cursor, comparisons: dict[str, list[str]] = COMPARISONS) -> list[TableComparison]:
    results = []
    for table, columns in comparisons.items():
        query = f"select {', '.join(columns)} from {table}"
        rows_a = duckdb_con.execute(query).fetchall()
        snowflake_cursor.execute(query)
        rows_b = snowflake_cursor.fetchall()
        results.append(compare_rows(table, rows_a, rows_b))
    return results
