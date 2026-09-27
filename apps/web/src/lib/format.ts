export const ROUND_TYPE_LABEL: Record<string, string> = {
  coding: "Coding",
  system_design: "System design",
  low_level_design: "Low-level design",
  tech_deep_dive: "Technical deep dive",
  hiring_manager: "Hiring manager (technical)",
  topic: "Topic deep dive",
};

export const VERDICT_LABEL: Record<string, { label: string; tone: string }> = {
  strong_hire: { label: "Strong hire", tone: "green" },
  hire: { label: "Hire", tone: "green" },
  lean_hire: { label: "Lean hire", tone: "amber" },
  lean_no_hire: { label: "Lean no hire", tone: "amber" },
  no_hire: { label: "No hire", tone: "red" },
};

export const ROUND_STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  pending: { label: "Not started", tone: "slate" },
  in_progress: { label: "In progress", tone: "indigo" },
  completed: { label: "Evaluating", tone: "indigo" },
  evaluated: { label: "Report ready", tone: "green" },
  insufficient: { label: "Too short to grade", tone: "amber" },
  eval_failed: { label: "Evaluation failed", tone: "red" },
};

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
