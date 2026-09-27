"""The four AI jobs the API runs: parse resume, parse JD + gap map, plan the loop, evaluate."""

import json
from typing import Any

from pydantic import BaseModel

from app.llm.client import structured
from app.llm.schemas import Evaluation, GapMap, InterviewPlan, JDProfile, ResumeProfile

MAX_DOC_CHARS = 30_000

PARSER_SYSTEM = """You extract structured data from career documents for an interview-practice \
platform. Be faithful to the document: never invent employers, skills, dates or projects. \
If a field is missing, use an empty list or a short 'unknown' value."""


def parse_resume(text: str) -> ResumeProfile:
    return structured(
        system=PARSER_SYSTEM,
        user=f"Extract the candidate profile from this resume.\n\n<resume>\n"
        f"{text[:MAX_DOC_CHARS]}\n</resume>",
        schema=ResumeProfile,
        effort="low",
    )


def parse_jd(jd_text: str, company: str, role: str) -> JDProfile:
    return structured(
        system=PARSER_SYSTEM,
        user=f"Company: {company}\nRole: {role}\n\nExtract the job requirements.\n\n"
        f"<job_description>\n{jd_text[:MAX_DOC_CHARS]}\n</job_description>",
        schema=JDProfile,
        effort="low",
    )


GAP_SYSTEM = """You are a senior technical recruiter preparing interviewers. Compare a \
candidate's resume with a job's requirements and decide where the interview should dig: \
claims on the resume worth verifying in depth, and JD requirements the resume does not show."""


def build_gap_map(resume: dict[str, Any], jd: dict[str, Any]) -> GapMap:
    return structured(
        system=GAP_SYSTEM,
        user=f"<resume_profile>\n{json.dumps(resume, indent=1)}\n</resume_profile>\n\n"
        f"<job_requirements>\n{json.dumps(jd, indent=1)}\n</job_requirements>",
        schema=GapMap,
        effort="medium",
    )


PLANNER_SYSTEM = """You design realistic technical interview loops for an interview-practice \
platform used by IT professionals and final-year students in India. A voice interviewer asks \
the questions; the candidate also has an on-screen problem panel, a code editor (with SQL \
support) and a whiteboard, exactly like a real video interview with a shared pad.

Rules:
- Produce exactly the rounds you are asked for, in order, with the given types and durations.
- Only technical rounds. Never include an HR, salary or culture-fit-only round.
- Make it hands-on, the way real interviewers do: in coding, SQL, data and topic rounds at \
least half the questions ask the candidate to WRITE a query or code in the editor (or draw \
on the whiteboard for design and data-modelling questions), then discuss it. Mix in short \
conceptual questions, but don't make the whole round "explain the logic".
- `prompt` is what the interviewer says aloud: 1-2 short conversational sentences with ONE \
ask, e.g. "Write a query that lists every customer with their total order amount, \
including customers with no orders. The tables are on your screen." Put every extra part of \
a multi-part question into follow_ups instead.
- `screen_text` carries the details a candidate would otherwise have to memorise: table \
schemas with column names and types, a few sample rows with expected output, input/output \
examples, constraints, or design requirements and scale. Never the solution.
- Hints go from a small nudge to a bigger one. None of them gives the full answer.
- SQL questions: the candidate can RUN queries against sample tables. Put DuckDB-compatible \
CREATE TABLE and INSERT statements in `setup_sql`, matching the schema in screen_text, with \
5-12 realistic rows that exercise edge cases (NULLs, ties, customers without orders, \
duplicates). Use standard types (INTEGER, VARCHAR, DATE, TIMESTAMP, DECIMAL(10,2)).
- Coding questions are asked "approach first": the prompt asks the candidate to explain \
their approach before writing code; the first follow-up asks them to implement it.
- When public_interview_reports are provided, match their question style, topics and \
difficulty for this company, without copying reported questions verbatim.
- Calibrate difficulty to the seniority level. Start with a warm-up, then ramp up.
- Plan roughly one main question per 10-15 minutes of a round (system design: one problem \
explored in depth). Rounds last 45-60 minutes, like real interviews.
- When a resume is provided, include at least one question per round grounded in the \
candidate's own projects or claims, and target the probe areas from the gap map.
- Adapt round content to the role: e.g. a data engineer's coding round can include SQL or \
Spark, and their design round can be a data pipeline or data model design.
- The rubric should have 3-5 dimensions relevant to the round type."""


def plan_loop(context: dict[str, Any], round_specs: list[dict[str, Any]]) -> InterviewPlan:
    return structured(
        system=PLANNER_SYSTEM,
        user=f"<candidate_and_job_context>\n{json.dumps(context, indent=1)}\n"
        f"</candidate_and_job_context>\n\n<rounds_to_plan>\n{json.dumps(round_specs, indent=1)}\n"
        "</rounds_to_plan>\n\nDesign the questions and rubric for each round.",
        schema=InterviewPlan,
        effort="high",
        max_tokens=32000,
    )


EVALUATOR_SYSTEM = """You are a calibrated, fair senior interviewer writing the debrief for \
one interview round on a practice platform. You grade only what is in the transcript and in \
the candidate's final editor and whiteboard content.

Rules:
- Score each rubric dimension 1-5 and support every score with short verbatim evidence \
quotes from the candidate's words or code. No evidence means you cannot score high.
- The transcript comes from speech-to-text: ignore transcription glitches and filler words \
when judging technical content (e.g. "city" is usually "CTE"), but do comment on clarity \
and structure.
- Account for hints: solving with no hints is stronger than solving after several hints. \
Mention hints in the relevant question feedback.
- If the round ended early or the candidate skipped questions, say so and score accordingly. \
The end reason is in the interviewer notes: "candidate_struggling" means the interviewer \
ended early because the candidate couldn't progress; "integrity" means it was ended after \
repeated integrity warnings, which you must state plainly in the summary.
- Coding: credit a clear approach explained before coding, and working code the candidate \
ran (run results are in the interviewer notes).
- Be direct and specific, like a good mentor. Feedback must be actionable.
- overall_score is 0-100 and must be consistent with the dimension scores and verdict \
(roughly: strong_hire >= 85, hire 70-84, lean_hire 60-69, lean_no_hire 45-59, no_hire < 45).
- The study plan should be 3-6 concrete items targeting the weakest areas."""


class _FixedSQL(BaseModel):
    setup_sql: str


def fix_setup_sql(schema_text: str, setup_sql: str, error: str) -> str:
    return structured(
        system="You fix DuckDB SQL scripts that create and populate sample tables.",
        user=f"<schema>\n{schema_text}\n</schema>\n\n<script>\n{setup_sql}\n</script>\n\n"
        f"DuckDB error: {error}\n\nReturn a corrected script that creates these tables and "
        "inserts the same sample rows.",
        schema=_FixedSQL,
        effort="low",
    ).setup_sql


def evaluate_round(
    round_plan: dict[str, Any],
    transcript: list[dict[str, Any]],
    workspace: dict[str, Any],
    context: dict[str, Any],
) -> Evaluation:
    """`workspace` holds final_code, final_whiteboard and the interviewer's notes."""
    lines = "\n".join(f"[{t.get('role', '?').upper()}] {t.get('text', '')}" for t in transcript)
    extra = ""
    if workspace.get("final_code"):
        extra += f"\n\n<final_code>\n{workspace['final_code']}\n</final_code>"
    if workspace.get("final_whiteboard"):
        extra += f"\n\n<final_whiteboard>\n{workspace['final_whiteboard']}\n</final_whiteboard>"
    if workspace.get("agent_notes"):
        notes = json.dumps(workspace["agent_notes"], indent=1)
        extra += f"\n\n<interviewer_notes>\n{notes}\n</interviewer_notes>"
    return structured(
        system=EVALUATOR_SYSTEM,
        user=f"<context>\n{json.dumps(context, indent=1)}\n</context>\n\n"
        f"<round_plan>\n{json.dumps(round_plan, indent=1)}\n</round_plan>\n\n"
        f"<transcript>\n{lines}\n</transcript>{extra}\n\nWrite the debrief.",
        schema=Evaluation,
        effort="high",
        max_tokens=32000,
    )
