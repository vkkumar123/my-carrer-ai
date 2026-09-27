"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Page } from "@/components/Nav";
import { Badge, Button, Card, ErrorNote, LinkButton, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { ROUND_TYPE_LABEL, VERDICT_LABEL } from "@/lib/format";
import type { Round } from "@/lib/types";

const INTEGRITY = {
  clean: { label: "Clean", tone: "green" },
  minor_concerns: { label: "Minor concerns", tone: "amber" },
  flagged: { label: "Flagged", tone: "red" },
} as const;

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full bg-indigo-500" style={{ width: `${(score / 5) * 100}%` }} />
      </div>
      <span className="text-sm tabular-nums text-slate-600">{score}/5</span>
    </div>
  );
}

export default function ReportPage() {
  const ready = useRequireAuth();
  const { id } = useParams<{ id: string }>();
  const [round, setRound] = useState<Round | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);

  const load = useCallback(() => api.getRound(id).then(setRound, (e) => setError(e.message)), [id]);
  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  const waiting = round?.status === "in_progress" || round?.status === "completed";
  useEffect(() => {
    if (!waiting) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [waiting, load]);

  if (!round) {
    return (
      <Page>
        <ErrorNote message={error} />
        {!error && <Spinner className="text-indigo-600" />}
      </Page>
    );
  }

  const ev = round.evaluation;
  const verdict = ev ? VERDICT_LABEL[ev.verdict] : null;
  const integrity = round.integrity;

  return (
    <Page>
      <LinkButton href={`/loops/${round.loop_id}`} variant="ghost" className="-ml-3 mb-2">
        ← Back to interview
      </LinkButton>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Round {round.index + 1} · {ROUND_TYPE_LABEL[round.type] ?? round.type}
      </p>
      <h1 className="text-2xl font-semibold">{round.title}</h1>

      {waiting && (
        <Card className="mt-6 flex items-center gap-3">
          <Spinner className="text-indigo-600" />
          <div>
            <p className="font-medium">Writing your debrief</p>
            <p className="text-sm text-slate-600">Your interviewer is reviewing the conversation. Usually under a minute.</p>
          </div>
        </Card>
      )}
      {round.status === "pending" && (
        <Card className="mt-6">
          <p className="font-medium">The interview was interrupted</p>
          <p className="mt-1 text-sm text-slate-600">
            Something went wrong on our side before the interview really started, so this round
            wasn&apos;t counted. You can start it again.
          </p>
          <LinkButton href={`/rounds/${round.id}/interview`} className="mt-3">
            Restart round
          </LinkButton>
        </Card>
      )}
      {round.status === "insufficient" && (
        <Card className="mt-6">
          <p className="font-medium">Not enough to grade</p>
          <p className="mt-1 text-sm text-slate-600">
            The round ended before you answered enough to evaluate. Start a new interview to try again.
          </p>
        </Card>
      )}
      {round.status === "eval_failed" && (
        <Card className="mt-6">
          <p className="font-medium">We couldn&apos;t generate the report.</p>
          <Button className="mt-3" onClick={() => api.retryEvaluation(round.id).then(setRound)}>
            Retry
          </Button>
        </Card>
      )}

      {ev && (
        <div className="mt-6 space-y-6">
          <Card>
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <p className="text-4xl font-bold text-slate-900">{ev.overall_score}</p>
                <p className="text-sm text-slate-500">out of 100</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {verdict && <Badge tone={verdict.tone}>{verdict.label}</Badge>}
                {integrity && (
                  <Badge tone={INTEGRITY[integrity.rating].tone}>
                    Integrity: {INTEGRITY[integrity.rating].label} ({integrity.score})
                  </Badge>
                )}
              </div>
            </div>
            <p className="mt-4 text-slate-700">{ev.summary}</p>
          </Card>

          <Card>
            <h2 className="font-semibold">Scores by skill</h2>
            <div className="mt-4 space-y-5">
              {ev.dimension_scores.map((d) => (
                <div key={d.dimension}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{d.dimension}</p>
                    <ScoreBar score={d.score} />
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{d.comment}</p>
                  {d.evidence.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {d.evidence.map((q, i) => (
                        <li key={i} className="border-l-2 border-slate-200 pl-3 text-sm italic text-slate-500">
                          &ldquo;{q}&rdquo;
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <h2 className="font-semibold text-emerald-700">What went well</h2>
              <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-700">
                {ev.strengths.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </Card>
            <Card>
              <h2 className="font-semibold text-amber-700">What to improve</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {ev.improvements.map((s) => (
                  <li key={s.area}>
                    <span className="font-medium">{s.area}:</span> {s.detail}
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <Card>
            <h2 className="font-semibold">Question by question</h2>
            <div className="mt-4 space-y-5">
              {ev.question_feedback.map((q, i) => (
                <div key={i} className="border-b border-slate-100 pb-5 last:border-0 last:pb-0">
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-medium">{q.question}</p>
                    <ScoreBar score={q.score} />
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    <span className="font-medium text-slate-800">You said: </span>
                    {q.answer_summary}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    <span className="font-medium text-slate-800">Feedback: </span>
                    {q.feedback}
                  </p>
                  <p className="mt-1 rounded-lg bg-indigo-50 p-3 text-sm text-indigo-900">
                    <span className="font-medium">A strong answer: </span>
                    {q.stronger_answer}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold">Your study plan</h2>
            <ol className="mt-3 list-inside list-decimal space-y-2 text-sm text-slate-700">
              {ev.study_plan.map((s) => (
                <li key={s.topic}>
                  <span className="font-medium">{s.topic}:</span> {s.action}
                </li>
              ))}
            </ol>
            <p className="mt-4 text-sm text-slate-600">
              <span className="font-medium text-slate-800">Communication: </span>
              {ev.communication_notes}
            </p>
          </Card>
        </div>
      )}

      {integrity && integrity.counts.length > 0 && (
        <Card className="mt-6">
          <h2 className="font-semibold">Integrity events</h2>
          <ul className="mt-3 space-y-1 text-sm text-slate-700">
            {integrity.counts.map((c) => (
              <li key={c.type}>
                {c.label}: {c.count}×
              </li>
            ))}
          </ul>
        </Card>
      )}

      {round.transcript && round.transcript.length > 0 && (
        <Card className="mt-6">
          <button className="font-semibold" onClick={() => setShowTranscript((v) => !v)}>
            {showTranscript ? "Hide" : "Show"} transcript
          </button>
          {showTranscript && (
            <div className="mt-4 space-y-2 text-sm">
              {round.transcript.map((t, i) => (
                <p key={i}>
                  <span className={t.role === "candidate" ? "font-medium text-emerald-700" : "font-medium text-indigo-700"}>
                    {t.role === "candidate" ? "You" : "Interviewer"}:
                  </span>{" "}
                  {t.text}
                </p>
              ))}
            </div>
          )}
          {showTranscript && round.final_code && (
            <>
              <p className="mt-4 text-sm font-medium">Your final code</p>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">{round.final_code}</pre>
            </>
          )}
          {showTranscript && round.final_whiteboard && (
            <>
              <p className="mt-4 text-sm font-medium">Your whiteboard (as the interviewer read it)</p>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-100 p-4 text-xs text-slate-800">
                {round.final_whiteboard}
              </pre>
            </>
          )}
        </Card>
      )}
    </Page>
  );
}
