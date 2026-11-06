"""The skill dictionary in Python (FR-TRN-05, FR-QA-06).

Uses the same ``transform/seeds/skills.csv`` and the same whole-word rule as the dbt
model ``slv_posting_skills``, so a resume and a posting are read the same way.
Extraction is local and needs no language model, which is what makes resume option C
possible (Q5): only the resulting skill list ever leaves this process.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache

from jobmarket.settings import REPO_ROOT

SKILLS_FILE = REPO_ROOT / "transform" / "seeds" / "skills.csv"


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    category: str
    pattern: re.Pattern[str]


@lru_cache
def dictionary() -> tuple[Skill, ...]:
    with SKILLS_FILE.open(newline="") as f:
        return tuple(
            Skill(
                r["skill_id"],
                r["skill_name"],
                r["category"],
                # identical to the SQL model: no letter or digit on either side
                re.compile(rf"(^|[^a-z0-9])({r['pattern']})([^a-z0-9]|$)"),
            )
            for r in csv.DictReader(f)
        )


def extract_skills(text: str) -> list[Skill]:
    lowered = text.lower()
    return [s for s in dictionary() if s.pattern.search(lowered)]


def canonical_skill(name: str) -> str | None:
    """'kafka' -> 'Apache Kafka'; None if the dictionary doesn't know it."""
    lowered = name.strip().lower()
    for s in dictionary():
        if s.name.lower() == lowered:
            return s.name
    found = extract_skills(name)
    return found[0].name if found else None
