"""Company interview blueprints: the *typical* round structure and interviewer style.

These describe publicly-discussed common patterns, not any company's official process.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DIR = Path(__file__).parent
DISCLAIMER = (
    "Based on commonly reported interview patterns. Not affiliated with or endorsed by the "
    "company; the real process may differ."
)
SENIOR_LEVELS = {"senior", "staff"}
ROUND_TYPES = {
    "coding",
    "system_design",
    "low_level_design",
    "tech_deep_dive",
    "hiring_manager",
    "topic",
}
# Company rounds run at real-interview length.
MIN_ROUND_MIN, MAX_ROUND_MIN = 45, 60
MAX_COMPANY_ROUNDS = 5


def clamp_duration(minutes: int) -> int:
    return max(MIN_ROUND_MIN, min(MAX_ROUND_MIN, int(minutes)))


@lru_cache
def _companies() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in sorted((_DIR / "companies").glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        data["slug"] = f.stem
        out[f.stem] = data
    return out


@lru_cache
def _templates() -> dict[str, Any]:
    return yaml.safe_load((_DIR / "templates.yaml").read_text())


def list_companies() -> list[dict[str, str]]:
    return [{"slug": s, "name": c["name"]} for s, c in _companies().items()]


def find_company(name: str) -> dict[str, Any] | None:
    key = name.strip().lower()
    for slug, c in _companies().items():
        names = {slug, c["name"].lower(), *[a.lower() for a in c.get("aliases", [])]}
        if key in names:
            return c
    return None


def rounds_for(blueprint_rounds: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
    senior = level in SENIOR_LEVELS
    picked = []
    for r in blueprint_rounds:
        if r.get("senior_only") and not senior:
            continue
        if r.get("junior_only") and senior:
            continue
        picked.append(
            {
                "type": r["type"],
                "title": r["title"],
                "duration_min": clamp_duration(r["duration_min"]),
            }
        )
    return picked


def rounds_from_research(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validated technical rounds from web research; empty when the research is unusable."""
    picked = [
        {
            "type": r["type"],
            "title": r["title"].strip()[:120],
            "duration_min": clamp_duration(r["duration_min"]),
        }
        for r in rounds
        if r.get("type") in ROUND_TYPES and r["type"] != "topic" and r.get("title", "").strip()
    ]
    return picked[:MAX_COMPANY_ROUNDS] if len(picked) >= 2 else []


def company_loop_spec(company: str, level: str) -> dict[str, Any]:
    """Round specs + persona for a company loop, falling back to the generic template."""
    bp = find_company(company)
    source = bp or _templates()["generic"]
    return {
        "company_known": bp is not None,
        "company_name": bp["name"] if bp else company.strip(),
        "persona": source["persona"],
        "rounds": rounds_for(source["rounds"], level),
        "disclaimer": DISCLAIMER,
    }


def topic_spec(topic: str, duration_min: int) -> dict[str, Any]:
    return {
        "persona": _templates()["topic"]["persona"],
        "rounds": [
            {"type": "topic", "title": f"{topic} - Deep Dive", "duration_min": duration_min}
        ],
    }
