export type Level = "intern" | "junior" | "mid" | "senior" | "staff";

export interface User {
  id: string;
  email: string;
  name: string | null;
}

export interface Resume {
  id: string;
  filename: string;
  parsed: {
    name?: string;
    headline?: string;
    years_experience?: number;
    skills?: string[];
  } | null;
  created_at: string;
}

export interface RoundSummary {
  id: string;
  index: number;
  type: string;
  title: string;
  duration_min: number;
  status: RoundStatus;
  overall_score: number | null;
  verdict: string | null;
}

export type RoundStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "evaluated"
  | "insufficient"
  | "eval_failed";

export interface GapMap {
  strengths: string[];
  gaps: string[];
  probe_areas: { area: string; reason: string }[];
}

export interface Loop {
  id: string;
  mode: "topic" | "company";
  title: string;
  company: string | null;
  role: string | null;
  level: Level;
  topic: string | null;
  status: "planning" | "ready" | "failed";
  gap_map: GapMap | null;
  disclaimer: string | null;
  research_sources: { url: string; title: string }[];
  created_at: string;
  rounds: RoundSummary[];
}

export interface Evaluation {
  overall_score: number;
  verdict: string;
  summary: string;
  dimension_scores: { dimension: string; score: number; evidence: string[]; comment: string }[];
  question_feedback: {
    question: string;
    answer_summary: string;
    score: number;
    feedback: string;
    stronger_answer: string;
  }[];
  strengths: string[];
  improvements: { area: string; detail: string }[];
  study_plan: { topic: string; action: string }[];
  communication_notes: string;
}

export interface Integrity {
  score: number;
  rating: "clean" | "minor_concerns" | "flagged";
  counts: { type: string; label: string; count: number }[];
  total_events: number;
}

export interface Round {
  id: string;
  loop_id: string;
  index: number;
  type: string;
  title: string;
  duration_min: number;
  status: RoundStatus;
  objective: string | null;
  started_at: string | null;
  ended_at: string | null;
  end_reason: string | null;
  plan: { questions: { id: string; prompt: string; what_good_looks_like: string }[] } | null;
  transcript: { role: "interviewer" | "candidate"; text: string }[] | null;
  final_code: string | null;
  final_whiteboard: string | null;
  evaluation: Evaluation | null;
  integrity: Integrity | null;
}

export interface JoinInfo {
  livekit_url: string;
  token: string;
  room: string;
  round: Round;
}

export type ProctorSeverity = "info" | "warn" | "critical";
export interface ProctorEvent {
  type: string;
  severity: ProctorSeverity;
  detail?: Record<string, unknown>;
  at?: string;
}
