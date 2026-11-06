"""Section-aware chunking of posting descriptions (FR-IDX-01, ADR-0007).

Strategy
  1. Split the description into sections at heading lines ("Responsibilities:",
     "What you'll need", "Qualifications"...).
  2. Drop boilerplate sections (equal-opportunity, privacy and accommodation notices):
     they are the same in every posting and only add noise to search.
  3. Pack sections into chunks of at most ``max_chars`` characters. Short sections are
     merged with the next one; long sections are split at line or sentence boundaries,
     with ``overlap_chars`` of the previous piece repeated so no requirement is cut in half.
  4. Every chunk starts with a header naming the job, so a chunk read on its own (by the
     embedding model or the LLM) still says which job it belongs to.

``CHUNKER_VERSION`` is recorded with every index build (FR-IDX-07); change it whenever
the strategy or its parameters change, and the index re-embeds everything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHUNKER_VERSION = "sections-v2"
MAX_CHARS = 1200
OVERLAP_CHARS = 200
MIN_SECTION_CHARS = 300

HEADING_WORDS = re.compile(
    r"\b(about|responsibilit|requirement|qualification|skills?|experience|what you|who you|you will|"
    r"you'll|we're looking|we are looking|nice to have|preferred|bonus|benefits|perks|why join|"
    r"the role|the team|role overview|job description|key|must have|education|location|work mode)",
    re.IGNORECASE,
)
BOILERPLATE = re.compile(
    r"equal (employment )?opportunit|\beeo\b|privacy (notice|policy)|accommodation|"
    r"discriminat|background check|e-verify|recruitment fraud|beware of",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Chunk:
    chunk_number: int
    section: str
    text: str  # what is embedded and shown: header + body


def is_heading(line: str) -> bool:
    line = line.strip().strip("*#•-\u2013 ").strip()
    if not line or len(line) > 70:
        return False
    if line.endswith(":"):
        return True
    words = len(line.split())
    looks_like_title = words <= 8 and not line.endswith((".", ",", ";"))
    return looks_like_title and bool(HEADING_WORDS.search(line) or BOILERPLATE.search(line))


def split_sections(description: str) -> list[tuple[str, str]]:
    """[(section name, body)] in order. Text before the first heading is the 'Overview'."""
    sections: list[tuple[str, list[str]]] = [("Overview", [])]
    for raw in description.splitlines():
        line = raw.strip()
        if not line:
            continue
        if is_heading(line):
            sections.append((line.strip("*#•-\u2013: ").strip(), []))
        else:
            sections[-1][1].append(line)
    return [(name, "\n".join(lines)) for name, lines in sections if lines]


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split at line ends, then sentence ends, then spaces; repeat ``overlap`` characters."""
    units = re.split(r"(?<=\n)|(?<=[.!?])\s+", text)
    pieces, current = [], ""
    for unit in units:
        while len(unit) > max_chars:  # a single unit longer than a chunk: cut at a space
            cut = unit.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            head, unit = unit[:cut], unit[cut:].lstrip()
            if current:
                pieces.append(current)
                current = ""
            pieces.append(head)
        if current and len(current) + len(unit) + 1 > max_chars:
            pieces.append(current)
            tail = current[-overlap:]
            current = tail[tail.find(" ") + 1 :] if " " in tail else tail
        current = f"{current} {unit}".strip() if current else unit.strip()
    if current:
        pieces.append(current)
    return [p.strip() for p in pieces if p.strip()]


def chunk_posting(
    title: str,
    company: str,
    city: str,
    description: str,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[Chunk]:
    header = f"{title} at {company} ({city})"
    body_budget = max_chars - len(header) - 40
    sections = [(n, b) for n, b in split_sections(description) if not BOILERPLATE.search(n)]

    # merge short sections forward so chunks aren't tiny
    merged: list[tuple[str, str]] = []
    for name, body in sections:
        if merged and len(merged[-1][1]) < MIN_SECTION_CHARS and len(merged[-1][1]) + len(body) < body_budget:
            prev_name, prev_body = merged[-1]
            merged[-1] = (prev_name, f"{prev_body}\n{name}:\n{body}")
        else:
            merged.append((name, body))

    chunks: list[Chunk] = []
    for name, body in merged:
        for piece in _split_long(body, body_budget, overlap_chars):
            chunks.append(Chunk(len(chunks), name, f"{header}\nSection: {name}\n{piece}"))
    if not chunks:  # no description at all: index the header so the job can still be found
        chunks.append(Chunk(0, "Overview", header))
    return chunks
