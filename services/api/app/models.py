import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class InterviewLoop(Base):
    """One practice session: a single topic round, or a full company loop of rounds."""

    __tablename__ = "interview_loops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(20))  # topic | company
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(20), default="mid")
    topic: Mapped[str | None] = mapped_column(String(200))
    jd_text: Mapped[str | None] = mapped_column(Text)
    jd_parsed: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    resume_id: Mapped[str | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))
    gap_map: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Blueprint output: {"persona": {...}, "rounds": [...], "disclaimer": str | None}
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped[User] = relationship()
    rounds: Mapped[list["Round"]] = relationship(
        back_populates="loop", order_by="Round.index", cascade="all, delete-orphan"
    )


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    loop_id: Mapped[str] = mapped_column(
        ForeignKey("interview_loops.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))  # coding | dsa | system_design | ...
    title: Mapped[str] = mapped_column(String(300))
    duration_min: Mapped[int] = mapped_column(Integer)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON)  # focus, questions, rubric
    # pending -> in_progress -> completed -> evaluated (or failed)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    livekit_room: Mapped[str | None] = mapped_column(String(200))
    # Interview language chosen in the lobby: english | hinglish
    language: Mapped[str] = mapped_column(String(10), default="english", server_default="english")
    voice: Mapped[str] = mapped_column(
        String(10), default="female", server_default="female"
    )  # interviewer voice
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(100))
    transcript: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    final_code: Mapped[str | None] = mapped_column(Text)
    final_whiteboard: Mapped[str | None] = mapped_column(Text)
    # From the interviewer: hints given and a one-line note per question.
    agent_notes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evaluation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    integrity: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    loop: Mapped[InterviewLoop] = relationship(back_populates="rounds")
    proctor_events: Mapped[list["ProctorEvent"]] = relationship(
        back_populates="round", order_by="ProctorEvent.at", cascade="all, delete-orphan"
    )


class ProctorEvent(Base):
    __tablename__ = "proctor_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(10))  # info | warn | critical
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    round: Mapped[Round] = relationship(back_populates="proctor_events")


class CompanyResearchCache(Base):
    """Web research on how a company interviews for a role family, shared across candidates."""

    __tablename__ = "company_research"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(200))
    role_family: Mapped[str] = mapped_column(String(50))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
