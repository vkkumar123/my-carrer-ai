"""Interview state machine. Pure logic, no LiveKit imports, so it is easy to test.

The LLM writes what the interviewer says; this module decides *where* the interview is:
which question is active, how much time is left, and when to wrap up or stop.
"""

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Phase(StrEnum):
    MAIN = "main"
    WRAP_UP = "wrap_up"  # last few minutes: finish current question, invite candidate questions
    OVERTIME = "overtime"  # past the scheduled end: close now


WRAP_UP_MIN = 5
GRACE_MIN = 2


@dataclass
class InterviewState:
    questions: list[dict[str, Any]]
    duration_min: int
    started_at: float = field(default_factory=time.monotonic)
    current: int = 0
    completed: list[str] = field(default_factory=list)
    ended: bool = False
    end_reason: str | None = None
    latest_code: str | None = None
    code_language: str | None = None

    def elapsed_min(self, now: float | None = None) -> float:
        return ((now or time.monotonic()) - self.started_at) / 60

    def remaining_min(self, now: float | None = None) -> float:
        return self.duration_min - self.elapsed_min(now)

    def phase(self, now: float | None = None) -> Phase:
        remaining = self.remaining_min(now)
        if remaining <= -GRACE_MIN:
            return Phase.OVERTIME
        if remaining <= min(WRAP_UP_MIN, self.duration_min * 0.2):
            return Phase.WRAP_UP
        return Phase.MAIN

    @property
    def current_question(self) -> dict[str, Any] | None:
        return self.questions[self.current] if self.current < len(self.questions) else None

    def advance(self, note: str = "") -> str:
        """Close the active question and return guidance for what to do next (tool result)."""
        q = self.current_question
        if q is not None:
            self.completed.append(q["id"])
            self.current += 1
        nxt = self.current_question
        remaining = max(0, round(self.remaining_min()))
        if nxt is None or self.phase() != Phase.MAIN:
            return (
                f"All planned questions are covered or time is nearly up ({remaining} min left). "
                "Begin wrapping up: ask if the candidate has any questions for you, answer "
                "briefly, then thank them and call end_interview."
            )
        per_q = remaining / max(1, len(self.questions) - self.current)
        return (
            f"Next question ({nxt['id']}, {nxt['difficulty']}, topic: {nxt['topic']}). "
            f"About {per_q:.0f} minutes available for it. Transition naturally, then ask: "
            f"{nxt['prompt']}"
        )

    def status_line(self) -> str:
        return (
            f"Time: {self.elapsed_min():.0f} of {self.duration_min} min used. "
            f"Question {min(self.current + 1, len(self.questions))} of {len(self.questions)}. "
            f"Phase: {self.phase().value}."
        )


# ---------------------------------------------------------------- proctoring

CRITICAL_PAUSE = {"screen_share_stopped", "camera_off", "multiple_faces"}

WARNING_TEXT = {
    "tab_hidden": "It looks like you switched away from the interview window. Please stay on "
    "this screen for the rest of the interview.",
    "window_blur": "The interview window lost focus. Please keep it in front.",
    "fullscreen_exit": "You've left fullscreen. Please return to fullscreen to continue.",
    "looking_away": "I notice you're looking away from the screen quite often. Please keep "
    "your attention here.",
    "no_face": "I can't see you on camera right now. Please make sure your face is visible.",
    "paste_blocked": "Pasting isn't allowed in the editor during the interview. Please type "
    "your solution.",
    "mic_muted": "Your microphone seems to be muted.",
}

PAUSE_TEXT = {
    "screen_share_stopped": "I've lost your screen share. Please share your entire screen "
    "again, and we'll continue from where we stopped.",
    "camera_off": "Your camera has turned off. Please turn it back on so we can continue.",
    "multiple_faces": "I can see more than one person on camera. This interview needs to be "
    "taken alone. Please make sure you're by yourself before we continue.",
}


@dataclass
class ProctorMonitor:
    """Decides when the interviewer should say something about a proctoring event.

    Minor events are only logged; repeated ones get a spoken warning (rate limited);
    critical ones pause the interview until the browser reports the issue resolved.
    """

    warn_after: int = 2  # occurrences within the window before we speak
    window_s: float = 120.0
    cooldown_s: float = 90.0
    paused_for: str | None = None
    _seen: dict[str, list[float]] = field(default_factory=dict)
    _last_spoken: float = -1e9

    def handle(self, event_type: str, now: float | None = None) -> str | None:
        """Return a line for the interviewer to say, or None."""
        now = time.monotonic() if now is None else now
        if event_type == "resumed":
            if self.paused_for is None:
                return None
            self.paused_for = None
            return "Thanks, that's sorted. Let's continue where we left off."

        if event_type in CRITICAL_PAUSE:
            if self.paused_for == event_type:
                return None
            self.paused_for = event_type
            self._last_spoken = now
            return PAUSE_TEXT[event_type]

        if event_type not in WARNING_TEXT:
            return None
        hits = [t for t in self._seen.get(event_type, []) if now - t <= self.window_s]
        hits.append(now)
        self._seen[event_type] = hits
        if len(hits) >= self.warn_after and now - self._last_spoken >= self.cooldown_s:
            self._last_spoken = now
            self._seen[event_type] = []
            return WARNING_TEXT[event_type]
        return None
