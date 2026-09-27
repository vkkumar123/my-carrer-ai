"""Interview state machine. Pure logic, no LiveKit imports, so it is easy to test.

The LLM writes what the interviewer says; this module decides *where* the interview is:
which question is active, how much time is left, and when to wrap up or stop.
"""

import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Phase(StrEnum):
    MAIN = "main"
    WRAP_UP = "wrap_up"  # last few minutes: finish current question, invite candidate questions
    OVERTIME = "overtime"  # past the scheduled end: close now


WRAP_UP_MIN = 5
GRACE_MIN = 2
EARLY_END_MIN = 25

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def speaks_hindi(text: str) -> bool:
    """True when a transcript turn is mostly Hindi (Devanagari script)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if _DEVANAGARI.match(c)) / len(letters) >= 0.3


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
    latest_whiteboard: str | None = None
    last_run: dict[str, Any] | None = None
    hints_used: dict[str, int] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

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
            if note:
                self.notes[q["id"]] = note
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
            f"The candidate's screen now shows question {self.current + 1} "
            f"({nxt['id']}, {nxt['difficulty']}, topic: {nxt['topic']}). About {per_q:.0f} "
            f"minutes available for it. Transition naturally, then ask: {nxt['prompt']}"
        )

    def next_hint(self) -> str:
        """Next unused hint for the active question (tool result)."""
        q = self.current_question
        if q is None:
            return "There is no active question. Don't give a hint."
        hints = q.get("hints") or []
        used = self.hints_used.get(q["id"], 0)
        if used >= len(hints):
            return (
                "No more prepared hints for this question. Give at most a small nudge in your "
                "own words without revealing the answer, or offer to move on."
            )
        self.hints_used[q["id"]] = used + 1
        return f"Hint {used + 1} of {len(hints)} (say it briefly, in your own words): {hints[used]}"

    def question_payload(self) -> dict[str, Any] | None:
        """What the candidate's screen shows for the active question."""
        q = self.current_question
        if q is None:
            return None
        return {
            "index": self.current,
            "total": len(self.questions),
            "id": q["id"],
            "topic": q.get("topic", ""),
            "prompt": q.get("prompt", ""),
            "screen_text": q.get("screen_text", ""),
            "workspace": q.get("workspace", "none"),
            "language": q.get("language", ""),
            "setup_sql": q.get("setup_sql", ""),
        }

    def workspace_view(self) -> str:
        """What the candidate currently has in the editor and on the whiteboard (tool result)."""
        parts = []
        if self.latest_code and self.latest_code.strip():
            parts.append(
                f"EDITOR ({self.code_language or 'unknown language'}):\n{self.latest_code}"
            )
        else:
            parts.append("EDITOR: empty.")
        if self.last_run:
            r = self.last_run
            status = "failed" if r.get("error") else "succeeded"
            parts.append(
                f"LAST RUN ({r.get('language', '?')}, {status}):\n"
                f"{r.get('error') or r.get('output') or '(no output)'}"
            )
        if self.latest_whiteboard and self.latest_whiteboard.strip():
            parts.append(f"WHITEBOARD:\n{self.latest_whiteboard}")
        else:
            parts.append("WHITEBOARD: empty.")
        return "\n\n".join(parts)

    def can_end_early(self, now: float | None = None) -> bool:
        """Real interviewers may wrap up early with a struggling candidate, but not at once."""
        return self.elapsed_min(now) >= min(EARLY_END_MIN, self.duration_min * 0.5)

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
class ProctorAction:
    kind: Literal["say", "pause", "end"]
    text: str


FINAL_WARNING = " This is your final warning. If it happens again, I'll have to end the interview."
END_TEXT = (
    "I'm going to stop the interview here because of repeated integrity issues: {reason}. "
    "You'll see the details in your report. Thank you for your time."
)


@dataclass
class ProctorMonitor:
    """Decides what the interviewer does about proctoring events.

    Minor events are only logged. Repeated ones get a spoken warning (rate limited). Critical
    ones pause the interview until the browser reports the issue resolved. Each warning or
    repeated critical issue is a strike: strike 1 warns, strike 2 is a final warning that says
    the next one ends the interview, strike 3 ends it.
    """

    warn_after: int = 2  # occurrences within the window before we speak
    window_s: float = 120.0
    cooldown_s: float = 90.0
    max_strikes: int = 3
    paused_for: str | None = None
    strikes: int = 0
    terminated_for: str | None = None
    _seen: dict[str, list[float]] = field(default_factory=dict)
    _critical_seen: dict[str, int] = field(default_factory=dict)
    _last_spoken: float = -1e9

    def _strike(self, event_type: str, warning: str) -> ProctorAction:
        self.strikes += 1
        if self.strikes >= self.max_strikes:
            self.terminated_for = event_type
            reason = LABELS.get(event_type, event_type)
            return ProctorAction("end", END_TEXT.format(reason=reason))
        if self.strikes == self.max_strikes - 1:
            warning += FINAL_WARNING
        return ProctorAction("say", warning)

    def handle(self, event_type: str, now: float | None = None) -> ProctorAction | None:
        """What the interviewer should do about this event, or None."""
        if self.terminated_for is not None:
            return None
        now = time.monotonic() if now is None else now
        if event_type == "resumed":
            if self.paused_for is None:
                return None
            self.paused_for = None
            return ProctorAction("say", "Thanks, that's sorted. Let's continue where we left off.")

        if event_type in CRITICAL_PAUSE:
            if self.paused_for == event_type:
                return None
            self.paused_for = event_type
            self._last_spoken = now
            seen = self._critical_seen.get(event_type, 0) + 1
            self._critical_seen[event_type] = seen
            # A second person on camera is never accidental; lost camera/screen once may be.
            if event_type == "multiple_faces" or seen > 1:
                action = self._strike(event_type, PAUSE_TEXT[event_type])
                return action if action.kind == "end" else ProctorAction("pause", action.text)
            return ProctorAction("pause", PAUSE_TEXT[event_type])

        if event_type not in WARNING_TEXT:
            return None
        hits = [t for t in self._seen.get(event_type, []) if now - t <= self.window_s]
        hits.append(now)
        self._seen[event_type] = hits
        if len(hits) >= self.warn_after and now - self._last_spoken >= self.cooldown_s:
            self._last_spoken = now
            self._seen[event_type] = []
            return self._strike(event_type, WARNING_TEXT[event_type])
        return None


LABELS = {
    "tab_hidden": "switching away from the interview window",
    "window_blur": "leaving the interview window",
    "fullscreen_exit": "leaving fullscreen",
    "looking_away": "looking away from the screen",
    "no_face": "not being visible on camera",
    "paste_blocked": "trying to paste into the editor",
    "mic_muted": "muting the microphone",
    "screen_share_stopped": "stopping the screen share",
    "camera_off": "turning the camera off",
    "multiple_faces": "another person being visible on camera",
}
