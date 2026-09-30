"""When should the interviewer speak? Pure logic, so every rule is unit-tested.

Real interviewers stay quiet while the candidate thinks or codes. They answer when the
candidate addresses them (a question, "done", "can you check", "hint?"), respond to an
explanation, and check in at most once after a long silence. This module makes that
decision before the LLM is asked for a reply.
"""

import re
import time
from dataclasses import dataclass
from typing import Literal

Kind = Literal["addressed", "working", "filler", "statement"]

# Candidate is talking TO the interviewer: asks something, says they're done, wants a hint.
# Question words only count at the start of the turn (after lead-ins like "so" or "okay"),
# so "the customer who didn't order" is not a question.
_LEAD = r"^(?:(?:so|okay|ok|and|but|then|um|uh|hmm|actually|sorry|sir|ma'?am)[,.]?\s+)*"
_ADDRESSED = re.compile(
    "|".join(
        [
            r"\?",
            _LEAD + r"(what|why|how|which|where|when|who|can|could|would|should|shall|do|does"
            r"|did|is|are|am|will|may)\b",
            r"\b(hint|help me|need help|stuck|clue|repeat|clarify|don'?t understand"
            r"|didn'?t (get|understand))\b",
            r"\b(check|see|look at|review) (it|this|now|my|the (query|code|output|result))\b",
            r"\btake a look\b|\b(skip|move on|next question|(end|stop) (the )?interview)\b",
            r"\b(i'?m|i am|it'?s|it is|am|all) (done|finished|complete)\b",
            r"\b(done|finished|completed)\s*[.!]?\s*$",
            r"\bi('| ha)?ve (written|done|updated|fixed|changed|run|ran|completed)\b",
            r"\bi (wrote|updated|fixed|ran)\b|\bwritten it\b|\bit('?s| is)? work(s|ing)\b",
            r"\b(correct|right)\s*[.!]?\s*$",
            # Hindi / Hinglish, romanised and Devanagari
            r"\b(kya|kaise|kyun|kyon|batao|bataiye|samjha(o|iye)?|ho ?gaya|sahi hai|hint do)\b",
            r"\bdekh(o|iye| lo| lijiye)\b",
            r"क्या|कैसे|क्यों|बताओ|बताइए|हो गया|देखो|देखिए|सही है",
        ]
    )
)

# Candidate says they're working: stay quiet until they come back.
_WORKING = re.compile(
    "|".join(
        [
            r"\b(let me|lemme) (write|code|type|try|think|check|see|fix|run|draw|work)",
            r"\b(i'?m|i am|am) (writing|coding|typing|trying|thinking|working|doing|fixing"
            r"|drawing|running)",
            r"\bgive me (a|one|some|two|2|a few) (minute|min|moment|second|sec|mins|minutes)",
            r"\b(one|a|1) (sec|second|minute|moment)\b|\bhold on\b|\bwait\b",
            r"\b(ek|do) (minute|min|second)\b|\bruk(o|iye|ie)\b|\bsoch(ne|ta|ti)\b",
            r"एक मिनट|रुको|रुकिए|सोचने",
        ]
    )
)

_FILLERS = {
    "hmm",
    "hmmm",
    "hm",
    "mm",
    "mmm",
    "um",
    "umm",
    "uh",
    "uhh",
    "ah",
    "oh",
    "okay",
    "ok",
    "okk",
    "yes",
    "yeah",
    "yep",
    "yup",
    "no",
    "nope",
    "right",
    "so",
    "sure",
    "fine",
    "alright",
    "cool",
    "got",
    "it",
    "i",
    "see",
    "thanks",
    "thank",
    "you",
    "haan",
    "han",
    "ha",
    "achha",
    "acha",
    "accha",
    "theek",
    "thik",
    "hai",
    "ji",
    "and",
    "then",
    "well",
    "like",
    "basically",
    "hello",
    "हाँ",
    "हां",
    "अच्छा",
    "ठीक",
    "है",
    "जी",
}

WORKSPACE_ACTIVE_S = 25  # typing/drawing within this window counts as working
SAID_WORKING_S = 120  # "let me write it" keeps the interviewer quiet this long
QUESTION_ANSWER_S = 20  # a short reply within this window may answer our question
CHECKIN_WORKING_S = 150  # minimum gap between check-ins during a hands-on task
IN_TASK_S = 300  # editor/whiteboard used this recently: they're in a hands-on task
CHECKIN_TALKING_S = 45
MAX_UNANSWERED_CHECKINS = 2


def _words(text: str) -> list[str]:
    return re.findall(r"[\w'ऀ-ॿ]+", text.lower())


def classify(text: str) -> Kind:
    t = text.strip().lower()
    if _ADDRESSED.search(t):
        return "addressed"
    if _WORKING.search(t):
        return "working"
    words = _words(t)
    if not words or all(w in _FILLERS for w in words) or len(words) <= 2:
        return "filler"
    return "statement"


@dataclass
class TurnPolicy:
    working_until: float = 0.0
    last_workspace_activity: float = -1e9
    last_question_at: float = -1e9  # when the interviewer last asked the candidate something
    last_checkin_at: float = -1e9
    unanswered_checkins: int = 0

    def working(self, now: float) -> bool:
        return now < self.working_until or now - self.last_workspace_activity < WORKSPACE_ACTIVE_S

    def note_workspace_activity(self, now: float | None = None) -> None:
        self.last_workspace_activity = time.monotonic() if now is None else now

    def note_interviewer_said(self, text: str, now: float | None = None) -> None:
        if text.strip().endswith("?"):
            self.last_question_at = time.monotonic() if now is None else now

    def should_reply(self, text: str, now: float | None = None) -> bool:
        """Decide whether this candidate turn needs the interviewer to speak."""
        now = time.monotonic() if now is None else now
        self.unanswered_checkins = 0
        kind = classify(text)
        if kind == "addressed":
            self.working_until = 0.0
            return True
        if kind == "working":
            self.working_until = now + SAID_WORKING_S
            return False
        if self.working(now):
            return False  # thinking aloud while coding: let them work
        if kind == "filler":
            # "Okay"/"Yes" can answer a question we just asked ("Are you ready?").
            return now - self.last_question_at < QUESTION_ANSWER_S
        return True  # an explanation or answer: respond to it

    def should_check_in(self, now: float | None = None) -> bool:
        """After a long silence: at most one check-in per window, and not forever."""
        now = time.monotonic() if now is None else now
        in_task = self.working(now) or now - self.last_workspace_activity < IN_TASK_S
        gap = CHECKIN_WORKING_S if in_task else CHECKIN_TALKING_S
        if now - self.last_checkin_at < gap or self.unanswered_checkins >= MAX_UNANSWERED_CHECKINS:
            return False
        self.last_checkin_at = now
        self.unanswered_checkins += 1
        return True
