"""Endpoints the voice agent calls. Protected by the shared X-Internal-Key header."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api_schemas import RoundCompleteIn
from app.auth import DB, require_internal_key
from app.models import Resume, Round
from app.services import pipeline

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_key)]
)


def _get_round(db: DB, round_id: str) -> Round:
    rnd = db.get(Round, round_id)
    if rnd is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return rnd


@router.get("/rounds/{round_id}/context")
def round_context(round_id: str, db: DB) -> dict[str, Any]:
    """Everything the interviewer needs to run the round."""
    rnd = _get_round(db, round_id)
    loop = rnd.loop
    resume = db.get(Resume, loop.resume_id) if loop.resume_id else None
    candidate = None
    if resume and resume.parsed:
        p = resume.parsed
        candidate = {
            "name": p.get("name"),
            "headline": p.get("headline"),
            "skills": p.get("skills", [])[:25],
            "projects": p.get("projects", [])[:5],
            "experiences": p.get("experiences", [])[:4],
        }
    return {
        "round_id": rnd.id,
        "status": rnd.status,
        "round_index": rnd.index,
        "total_rounds": len(loop.rounds),
        "type": rnd.type,
        "title": rnd.title,
        "duration_min": rnd.duration_min,
        "plan": rnd.plan,
        "mode": loop.mode,
        "company": loop.company,
        "role": loop.role,
        "topic": loop.topic,
        "level": loop.level,
        "persona": loop.spec["persona"],
        "voice": rnd.voice,
        "language": rnd.language,
        "candidate_name": loop.user.name,
        "candidate": candidate,
        "gap_map": loop.gap_map,
    }


@router.post("/rounds/{round_id}/complete", status_code=status.HTTP_202_ACCEPTED)
def complete_round(
    round_id: str, body: RoundCompleteIn, db: DB, background: BackgroundTasks
) -> dict[str, str]:
    rnd = _get_round(db, round_id)
    if rnd.status != "in_progress":
        return {"status": rnd.status}  # idempotent: agent may retry

    answered = sum(1 for t in body.transcript if t.role == "candidate")
    if body.end_reason == "agent_error" and answered < pipeline.MIN_CANDIDATE_TURNS:
        # Our failure, not the candidate's: give the round back so they can retry.
        rnd.status = "pending"
        rnd.livekit_room = None
        rnd.started_at = None
        db.commit()
        return {"status": "pending"}
    rnd.transcript = [t.model_dump() for t in body.transcript]
    rnd.final_code = body.final_code
    rnd.final_whiteboard = body.final_whiteboard
    rnd.agent_notes = {
        "end_reason": body.end_reason,
        "hints_used": body.hints_used,
        "question_notes": body.question_notes,
        "last_code_run": body.last_run,
    }
    rnd.end_reason = body.end_reason
    rnd.ended_at = datetime.now(UTC)
    rnd.status = "completed"
    db.commit()
    background.add_task(pipeline.evaluate_round, rnd.id)
    return {"status": "completed"}
