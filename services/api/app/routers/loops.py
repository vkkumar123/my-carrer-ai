from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import blueprints
from app.api_schemas import LoopCreate, LoopOut, RoundSummary
from app.auth import DB, CurrentUser
from app.models import InterviewLoop, Resume
from app.services import pipeline

router = APIRouter(prefix="/loops", tags=["loops"])


def loop_out(loop: InterviewLoop) -> LoopOut:
    return LoopOut(
        id=loop.id,
        mode=loop.mode,
        title=loop.title,
        company=loop.company,
        role=loop.role,
        level=loop.level,
        topic=loop.topic,
        status=loop.status,
        gap_map=loop.gap_map,
        disclaimer=loop.spec.get("disclaimer"),
        research_sources=loop.spec.get("research_sources", []),
        created_at=loop.created_at,
        rounds=[
            RoundSummary(
                id=r.id,
                index=r.index,
                type=r.type,
                title=r.title,
                duration_min=r.duration_min,
                status=r.status,
                overall_score=(r.evaluation or {}).get("overall_score"),
                verdict=(r.evaluation or {}).get("verdict"),
            )
            for r in loop.rounds
        ],
    )


@router.get("/companies")
def companies() -> list[dict[str, str]]:
    """Companies with a curated blueprint. Any other company falls back to a generic loop."""
    return blueprints.list_companies()


@router.post("", response_model=LoopOut, status_code=status.HTTP_202_ACCEPTED)
def create_loop(
    body: LoopCreate, user: CurrentUser, db: DB, background: BackgroundTasks
) -> LoopOut:
    if body.resume_id:
        resume = db.get(Resume, body.resume_id)
        if resume is None or resume.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")

    if body.mode == "topic":
        topic = body.topic.strip()
        spec = blueprints.topic_spec(topic, body.duration_min)
        loop = InterviewLoop(
            user_id=user.id,
            mode="topic",
            title=f"{topic} practice",
            topic=topic,
            level=body.level,
            resume_id=body.resume_id,
            spec=spec,
            status="planning",
        )
    else:
        spec = blueprints.company_loop_spec(body.company, body.level)
        company = spec["company_name"]
        loop = InterviewLoop(
            user_id=user.id,
            mode="company",
            title=f"{company} - {body.role.strip()}",
            company=company,
            role=body.role.strip(),
            level=body.level,
            jd_text=body.jd_text,
            resume_id=body.resume_id,
            spec=spec,
            status="planning",
        )
    db.add(loop)
    db.commit()
    background.add_task(pipeline.plan_loop, loop.id)
    return loop_out(loop)


def _get_owned_loop(db: DB, loop_id: str, user_id: str) -> InterviewLoop:
    loop = db.get(InterviewLoop, loop_id, options=[selectinload(InterviewLoop.rounds)])
    if loop is None or loop.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return loop


@router.get("", response_model=list[LoopOut])
def list_loops(user: CurrentUser, db: DB) -> list[LoopOut]:
    rows = db.scalars(
        select(InterviewLoop)
        .where(InterviewLoop.user_id == user.id)
        .options(selectinload(InterviewLoop.rounds))
        .order_by(InterviewLoop.created_at.desc())
    )
    return [loop_out(loop) for loop in rows]


@router.get("/{loop_id}", response_model=LoopOut)
def get_loop(loop_id: str, user: CurrentUser, db: DB) -> LoopOut:
    return loop_out(_get_owned_loop(db, loop_id, user.id))


@router.post("/{loop_id}/retry", response_model=LoopOut, status_code=status.HTTP_202_ACCEPTED)
def retry_planning(loop_id: str, user: CurrentUser, db: DB, background: BackgroundTasks) -> LoopOut:
    loop = _get_owned_loop(db, loop_id, user.id)
    if loop.status != "failed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed plans can be retried")
    loop.status = "planning"
    db.commit()
    background.add_task(pipeline.plan_loop, loop.id)
    return loop_out(loop)


@router.delete("/{loop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loop(loop_id: str, user: CurrentUser, db: DB) -> None:
    db.delete(_get_owned_loop(db, loop_id, user.id))
    db.commit()
