import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api_schemas import JoinOut, ProctorBatchIn, RoundOut
from app.auth import DB, CurrentUser
from app.config import get_settings
from app.livekit_service import participant_token
from app.models import ProctorEvent, Round
from app.services import pipeline

router = APIRouter(prefix="/rounds", tags=["rounds"])

FINISHED = {"completed", "evaluated", "insufficient", "eval_failed"}


def round_out(r: Round) -> RoundOut:
    finished = r.status in FINISHED
    return RoundOut(
        id=r.id,
        loop_id=r.loop_id,
        index=r.index,
        type=r.type,
        title=r.title,
        duration_min=r.duration_min,
        status=r.status,
        objective=r.plan.get("objective"),
        started_at=r.started_at,
        ended_at=r.ended_at,
        end_reason=r.end_reason,
        plan=r.plan if finished else None,
        transcript=r.transcript if finished else None,
        final_code=r.final_code if finished else None,
        final_whiteboard=r.final_whiteboard if finished else None,
        evaluation=r.evaluation,
        integrity=r.integrity,
    )


def _get_owned_round(db: DB, round_id: str, user_id: str) -> Round:
    rnd = db.get(Round, round_id)
    if rnd is None or rnd.loop.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Round not found")
    return rnd


@router.get("/{round_id}", response_model=RoundOut)
def get_round(round_id: str, user: CurrentUser, db: DB) -> RoundOut:
    return round_out(_get_owned_round(db, round_id, user.id))


@router.post("/{round_id}/join", response_model=JoinOut)
def join_round(round_id: str, user: CurrentUser, db: DB) -> JoinOut:
    """Start (or rejoin) a round: returns a LiveKit token that also summons the AI interviewer."""
    rnd = _get_owned_round(db, round_id, user.id)
    if rnd.status not in {"pending", "in_progress"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "This round has already finished")
    if rnd.status == "pending":
        rnd.status = "in_progress"
        rnd.started_at = datetime.now(UTC)
        rnd.livekit_room = f"round-{rnd.id}-{uuid.uuid4().hex[:6]}"
        db.commit()

    token = participant_token(
        room=rnd.livekit_room,
        identity=f"candidate-{user.id}",
        name=user.name or user.email.split("@")[0],
        round_id=rnd.id,
    )
    return JoinOut(
        livekit_url=get_settings().livekit_url,
        token=token,
        room=rnd.livekit_room,
        round=round_out(rnd),
    )


@router.post("/{round_id}/proctor-events", status_code=status.HTTP_204_NO_CONTENT)
def add_proctor_events(round_id: str, body: ProctorBatchIn, user: CurrentUser, db: DB) -> None:
    rnd = _get_owned_round(db, round_id, user.id)
    if rnd.status != "in_progress":
        # Late events from a closing tab are harmless; just drop them.
        return
    now = datetime.now(UTC)
    for e in body.events:
        db.add(
            ProctorEvent(
                round_id=rnd.id,
                type=e.type,
                severity=e.severity,
                detail=e.detail,
                at=min(e.at or now, now),
            )
        )
    db.commit()


@router.post("/{round_id}/evaluate", response_model=RoundOut, status_code=status.HTTP_202_ACCEPTED)
def retry_evaluation(
    round_id: str, user: CurrentUser, db: DB, background: BackgroundTasks
) -> RoundOut:
    rnd = _get_owned_round(db, round_id, user.id)
    if rnd.status != "eval_failed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed evaluations can be retried")
    rnd.status = "completed"
    db.commit()
    background.add_task(pipeline.evaluate_round, rnd.id)
    return round_out(rnd)
