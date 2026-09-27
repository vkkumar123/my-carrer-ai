from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

Level = Literal["intern", "junior", "mid", "senior", "staff"]


class DevLoginIn(BaseModel):
    email: EmailStr
    name: str | None = None


class TokenOut(BaseModel):
    access_token: str
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None


class ResumeOut(BaseModel):
    id: str
    filename: str
    parsed: dict[str, Any] | None
    created_at: datetime


class LoopCreate(BaseModel):
    mode: Literal["topic", "company"]
    level: Level = "mid"
    # topic mode
    topic: str | None = Field(default=None, max_length=200)
    duration_min: int = Field(default=30, ge=15, le=60)
    # company mode
    company: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    jd_text: str | None = Field(default=None, max_length=30_000)
    resume_id: str | None = None

    @model_validator(mode="after")
    def _check_mode_fields(self) -> "LoopCreate":
        if self.mode == "topic" and not (self.topic and self.topic.strip()):
            raise ValueError("topic is required for topic practice")
        if self.mode == "company" and not (self.company and self.role):
            raise ValueError("company and role are required for a company loop")
        return self


class RoundSummary(BaseModel):
    id: str
    index: int
    type: str
    title: str
    duration_min: int
    status: str
    overall_score: int | None = None
    verdict: str | None = None


class LoopOut(BaseModel):
    id: str
    mode: str
    title: str
    company: str | None
    role: str | None
    level: str
    topic: str | None
    status: str
    gap_map: dict[str, Any] | None
    disclaimer: str | None = None
    created_at: datetime
    rounds: list[RoundSummary]


class RoundOut(BaseModel):
    id: str
    loop_id: str
    index: int
    type: str
    title: str
    duration_min: int
    status: str
    objective: str | None
    started_at: datetime | None
    ended_at: datetime | None
    end_reason: str | None
    # Only filled in after the round ends, so candidates can't read questions in advance.
    plan: dict[str, Any] | None = None
    transcript: list[dict[str, Any]] | None = None
    final_code: str | None = None
    evaluation: dict[str, Any] | None = None
    integrity: dict[str, Any] | None = None


class JoinOut(BaseModel):
    livekit_url: str
    token: str
    room: str
    round: RoundOut


ProctorType = Literal[
    "camera_off",
    "screen_share_stopped",
    "no_face",
    "multiple_faces",
    "looking_away",
    "tab_hidden",
    "window_blur",
    "fullscreen_exit",
    "paste_blocked",
    "extra_display",
    "mic_muted",
    "resumed",
]


class ProctorEventIn(BaseModel):
    type: ProctorType
    severity: Literal["info", "warn", "critical"]
    detail: dict[str, Any] | None = None
    at: datetime | None = None


class ProctorBatchIn(BaseModel):
    events: list[ProctorEventIn] = Field(max_length=200)


# ---- internal (agent <-> api) ----


class TranscriptTurn(BaseModel):
    role: Literal["interviewer", "candidate"]
    text: str
    at: float | None = None


class RoundCompleteIn(BaseModel):
    transcript: list[TranscriptTurn]
    final_code: str | None = Field(default=None, max_length=50_000)
    end_reason: str = "completed"
