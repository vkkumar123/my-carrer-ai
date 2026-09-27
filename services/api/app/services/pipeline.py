"""Background work: planning a loop and evaluating a finished round.

Runs via FastAPI BackgroundTasks, so on Cloud Run the service must keep CPU allocated
after the response (`--no-cpu-throttling`). Move to Cloud Tasks when volume grows.
"""

import logging
from typing import Any

from app.db import SessionLocal
from app.integrity import compute_integrity
from app.llm import tasks
from app.llm.client import LLMError
from app.models import InterviewLoop, Resume, Round

log = logging.getLogger(__name__)

MIN_CANDIDATE_TURNS = 3


def loop_context(loop: InterviewLoop, resume: Resume | None) -> dict[str, Any]:
    ctx: dict[str, Any] = {"mode": loop.mode, "level": loop.level}
    if loop.mode == "topic":
        ctx["topic"] = loop.topic
    else:
        ctx.update(company=loop.company, role=loop.role)
        if loop.jd_parsed:
            ctx["job_requirements"] = loop.jd_parsed
        if loop.gap_map:
            ctx["gap_map"] = loop.gap_map
    ctx["interviewer_style"] = loop.spec["persona"]["style"]
    if resume and resume.parsed:
        ctx["candidate_resume"] = resume.parsed
    return ctx


def plan_loop(loop_id: str) -> None:
    with SessionLocal() as db:
        loop = db.get(InterviewLoop, loop_id)
        if loop is None:
            return
        resume = db.get(Resume, loop.resume_id) if loop.resume_id else None
        try:
            if loop.mode == "company" and loop.jd_text:
                loop.jd_parsed = tasks.parse_jd(
                    loop.jd_text, loop.company or "", loop.role or ""
                ).model_dump()
                if resume and resume.parsed:
                    loop.gap_map = tasks.build_gap_map(resume.parsed, loop.jd_parsed).model_dump()

            round_specs = loop.spec["rounds"]
            plan = tasks.plan_loop(loop_context(loop, resume), round_specs)
            if len(plan.rounds) != len(round_specs):
                raise LLMError(
                    f"planner returned {len(plan.rounds)} rounds, expected {len(round_specs)}"
                )

            for i, (rs, rp) in enumerate(zip(round_specs, plan.rounds, strict=True)):
                loop.rounds.append(
                    Round(
                        index=i,
                        type=rs["type"],
                        title=rs["title"],
                        duration_min=rs["duration_min"],
                        plan=rp.model_dump(),
                    )
                )
            loop.status = "ready"
        except Exception:  # background job: always land in a final state
            log.exception("planning failed for loop %s", loop_id)
            db.rollback()
            loop = db.get(InterviewLoop, loop_id)
            loop.status = "failed"
        db.commit()


def evaluate_round(round_id: str) -> None:
    with SessionLocal() as db:
        rnd = db.get(Round, round_id)
        if rnd is None:
            return
        rnd.integrity = compute_integrity(rnd.proctor_events)
        turns = rnd.transcript or []
        if sum(1 for t in turns if t.get("role") == "candidate") < MIN_CANDIDATE_TURNS:
            rnd.status = "insufficient"
            db.commit()
            return

        loop = rnd.loop
        resume = db.get(Resume, loop.resume_id) if loop.resume_id else None
        try:
            workspace = {
                "final_code": rnd.final_code,
                "final_whiteboard": rnd.final_whiteboard,
                "agent_notes": rnd.agent_notes,
            }
            ev = tasks.evaluate_round(rnd.plan, turns, workspace, loop_context(loop, resume))
            rnd.evaluation = ev.model_dump()
            rnd.status = "evaluated"
        except Exception:  # background job: always land in a final state
            log.exception("evaluation failed for round %s", round_id)
            db.rollback()
            rnd = db.get(Round, round_id)
            rnd.status = "eval_failed"
        db.commit()
