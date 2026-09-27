"""Schemas the LLM must fill. Kept flat and simple so structured outputs stay reliable."""

from typing import Literal

from pydantic import BaseModel, Field

# ---------- Resume / JD ----------


class Experience(BaseModel):
    company: str
    title: str
    duration: str = Field(description="e.g. 'Jan 2021 - Present' or '2 years'")
    highlights: list[str]


class Project(BaseModel):
    name: str
    summary: str
    tech: list[str]


class ResumeProfile(BaseModel):
    name: str
    headline: str = Field(description="One-line summary, e.g. 'Data Engineer, 4 yrs, Spark/AWS'")
    years_experience: float
    skills: list[str]
    experiences: list[Experience]
    projects: list[Project]
    education: list[str]


class JDProfile(BaseModel):
    title: str
    company: str
    seniority: Literal["intern", "junior", "mid", "senior", "staff"]
    must_have: list[str]
    nice_to_have: list[str]
    responsibilities: list[str]


class ProbeArea(BaseModel):
    area: str
    reason: str


class GapMap(BaseModel):
    strengths: list[str] = Field(description="JD requirements the resume clearly shows")
    gaps: list[str] = Field(description="JD requirements the resume does not show")
    probe_areas: list[ProbeArea] = Field(
        description="Where a real interviewer would dig: claims to verify and gaps to test"
    )


# ---------- Interview plan ----------

RoundType = Literal[
    "coding", "system_design", "low_level_design", "tech_deep_dive", "hiring_manager", "topic"
]


class PlannedQuestion(BaseModel):
    id: str = Field(description="Short id like 'q1'")
    prompt: str = Field(description="The question exactly as the interviewer will ask it aloud")
    topic: str
    difficulty: Literal["easy", "medium", "hard"]
    follow_ups: list[str] = Field(description="2-4 probing follow-ups, harder as they go")
    what_good_looks_like: str = Field(description="Key points of a strong answer (never shown)")


class RubricItem(BaseModel):
    dimension: str
    weight: int = Field(description="Relative weight, 1-5")
    description: str = Field(description="What a 5/5 looks like for this dimension")


class RoundPlan(BaseModel):
    type: RoundType
    title: str
    duration_min: int
    objective: str
    questions: list[PlannedQuestion]
    rubric: list[RubricItem]


class InterviewPlan(BaseModel):
    rounds: list[RoundPlan]


# ---------- Evaluation ----------


class DimensionScore(BaseModel):
    dimension: str
    score: int = Field(description="1 (poor) to 5 (excellent)")
    evidence: list[str] = Field(description="Short verbatim quotes from the transcript")
    comment: str


class QuestionFeedback(BaseModel):
    question: str
    answer_summary: str
    score: int = Field(description="1 to 5")
    feedback: str
    stronger_answer: str = Field(description="What a strong candidate would have said")


class Improvement(BaseModel):
    area: str
    detail: str


class StudyItem(BaseModel):
    topic: str
    action: str = Field(description="Concrete next step, e.g. 'Solve 5 sliding-window problems'")


class Evaluation(BaseModel):
    overall_score: int = Field(description="0 to 100")
    verdict: Literal["strong_hire", "hire", "lean_hire", "lean_no_hire", "no_hire"]
    summary: str
    dimension_scores: list[DimensionScore]
    question_feedback: list[QuestionFeedback]
    strengths: list[str]
    improvements: list[Improvement]
    study_plan: list[StudyItem]
    communication_notes: str = Field(description="Clarity, structure, filler words, pace")
