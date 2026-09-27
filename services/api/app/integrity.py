"""Turns proctoring events into an integrity score for the report."""

from collections import Counter
from typing import Any

from app.models import ProctorEvent

PENALTY = {"info": 0, "warn": 3, "critical": 10}

LABELS = {
    "camera_off": "Camera turned off",
    "screen_share_stopped": "Screen sharing stopped",
    "no_face": "No face visible",
    "multiple_faces": "More than one person visible",
    "looking_away": "Looking away from the screen",
    "tab_hidden": "Switched tab or window",
    "window_blur": "Interview window lost focus",
    "fullscreen_exit": "Left fullscreen",
    "paste_blocked": "Tried to paste into the editor",
    "extra_display": "Additional display connected",
    "mic_muted": "Microphone muted",
}


def compute_integrity(events: list[ProctorEvent]) -> dict[str, Any]:
    counts = Counter(e.type for e in events if e.severity != "info")
    penalty = sum(PENALTY.get(e.severity, 0) for e in events)
    score = max(0, 100 - penalty)
    if score >= 85:
        rating = "clean"
    elif score >= 60:
        rating = "minor_concerns"
    else:
        rating = "flagged"
    return {
        "score": score,
        "rating": rating,
        "counts": [
            {"type": t, "label": LABELS.get(t, t), "count": n} for t, n in counts.most_common()
        ],
        "total_events": len(events),
    }
