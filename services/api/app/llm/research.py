"""How does <company> interview for <role>? Researched on the open web, cached and shared."""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import structured, web_research
from app.llm.schemas import CompanyResearch
from app.models import CompanyResearchCache

log = logging.getLogger(__name__)

CACHE_DAYS = 30

ROLE_FAMILIES = [
    ("data_engineer", ["data engineer", "etl", "big data", "spark"]),
    ("data_analyst", ["data analyst", "business analyst", "bi ", "analytics"]),
    ("data_scientist", ["data scientist", "machine learning", "ml ", "ai engineer"]),
    ("frontend", ["frontend", "front end", "front-end", "react", "ui engineer"]),
    ("mobile", ["android", "ios", "mobile"]),
    ("devops", ["devops", "sre", "site reliability", "platform engineer", "cloud engineer"]),
    ("qa", ["qa", "test", "sdet", "quality"]),
    ("engineering_manager", ["engineering manager", "em ", "tech lead manager"]),
]


def role_family(role: str) -> str:
    r = f" {role.lower()} "
    for family, words in ROLE_FAMILIES:
        if any(w in r for w in words):
            return family
    return "software_engineer"


def _key(company: str, family: str) -> str:
    return f"{re.sub(r'[^a-z0-9]+', '-', company.lower()).strip('-')}|{family}"


RESEARCH_SYSTEM = """You research how a company runs technical interviews, for an \
interview-practice platform in India. Search the open web: Reddit, LeetCode Discuss, \
Glassdoor-style interview reviews, GeeksforGeeks interview experiences, blogs, and public \
LinkedIn posts. Prefer reports from the last 2-3 years and from India when available.

Write concise findings covering: the typical technical rounds in order (type, rough length, \
focus), the interviewer style, the topics that come up most, several paraphrased example \
questions, and how hard candidates found it. Note when reports disagree or are thin. Do not \
copy long passages; summarise."""


def _research(company: str, role: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    notes, sources = web_research(
        system=RESEARCH_SYSTEM,
        user=f"How does {company} interview candidates for a {role} role? Focus on the "
        "technical rounds.",
    )
    data = structured(
        system="Extract structured interview research from the findings. Only include what "
        "the findings support.",
        user=f"Company: {company}\nRole: {role}\n\n<findings>\n{notes}\n</findings>",
        schema=CompanyResearch,
        effort="low",
    )
    return data.model_dump(), sources


def get_company_research(db: Session, company: str, role: str) -> dict[str, Any] | None:
    """Cached research for company + role family, researching on a miss. None on failure."""
    family = role_family(role)
    key = _key(company, family)
    row = db.scalar(select(CompanyResearchCache).where(CompanyResearchCache.key == key))
    fresh_after = datetime.now(UTC) - timedelta(days=CACHE_DAYS)
    if row is not None:
        created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
        if created >= fresh_after:
            return row.data | {"sources": row.sources}

    try:
        data, sources = _research(company, role)
    except Exception:  # research is optional: fall back to the blueprint on any failure
        log.exception("company research failed for %s", key)
        return row.data | {"sources": row.sources} if row is not None else None

    if row is None:
        row = CompanyResearchCache(key=key, company=company, role_family=family)
        db.add(row)
    row.data, row.sources, row.created_at = data, sources, datetime.now(UTC)
    db.flush()
    return data | {"sources": sources}
