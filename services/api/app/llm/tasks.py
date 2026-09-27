"""The four AI jobs the API runs: parse resume, parse JD + gap map, plan the loop, evaluate."""

import json
from typing import Any

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
platform used by IT professionals and final-year students in India.

Rules:
- Produce exactly the rounds you are asked for, in order, with the given types and durations.
- Only technical rounds. Never include an HR, salary or culture-fit-only round.
- Questions must be spoken aloud by a voice interviewer: phrase them conversationally, no \
markdown, no code blocks, no ASCII diagrams. For coding rounds, describe the problem clearly \
in words, including one small example input and output.
- Calibrate difficulty to the seniority level. Start with a warm-up question, then ramp up.
- Plan roughly one main question per 10-12 minutes of a round (coding: 1-2 problems; system \
design: 1 problem explored in depth).
- When a resume is provided, include at least one question per round grounded in the \
candidate's own projects or claims, and target the probe areas from the gap map.
- Adapt round content to the role: e.g. a data engineer's coding round can include SQL or \
Spark, and their design round can be a data pipeline design.
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
one interview round on a practice platform. You grade only what is in the transcript.

Rules:
- Score each rubric dimension 1-5 and support every score with short verbatim evidence \
quotes from the candidate's words. No evidence means you cannot score high.
- The transcript comes from speech-to-text: ignore transcription glitches and filler words \
when judging technical content, but do comment on clarity and structure.
- If the round ended early or the candidate barely spoke, say so and score accordingly.
- Be direct and specific, like a good mentor. Feedback must be actionable.
- overall_score is 0-100 and must be consistent with the dimension scores and verdict \
(roughly: strong_hire >= 85, hire 70-84, lean_hire 60-69, lean_no_hire 45-59, no_hire < 45).
- The study plan should be 3-6 concrete items targeting the weakest areas."""


def evaluate_round(
    round_plan: dict[str, Any],
    transcript: list[dict[str, Any]],
    final_code: str | None,
    context: dict[str, Any],
) -> Evaluation:
    lines = "\n".join(f"[{t.get('role', '?').upper()}] {t.get('text', '')}" for t in transcript)
    code_part = f"\n\n<final_code>\n{final_code}\n</final_code>" if final_code else ""
    return structured(
        system=EVALUATOR_SYSTEM,
        user=f"<context>\n{json.dumps(context, indent=1)}\n</context>\n\n"
        f"<round_plan>\n{json.dumps(round_plan, indent=1)}\n</round_plan>\n\n"
        f"<transcript>\n{lines}\n</transcript>{code_part}\n\nWrite the debrief.",
        schema=Evaluation,
        effort="high",
        max_tokens=32000,
    )
