"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Page } from "@/components/Nav";
import { Badge, Button, Card, ErrorNote, LinkButton, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { ROUND_STATUS_LABEL, ROUND_TYPE_LABEL, VERDICT_LABEL } from "@/lib/format";
import type { Loop } from "@/lib/types";

export default function LoopPage() {
  const ready = useRequireAuth();
  const { id } = useParams<{ id: string }>();
  const [loop, setLoop] = useState<Loop | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      api.getLoop(id).then(
        (l) => {
          setLoop(l);
          setError(null);
        },
        (e) => {
          setError(e.message);
          setLoop(null); // stops polling a loop we can't read (e.g. signed in as someone else)
        },
      ),
    [id],
  );

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  // Poll while the AI is preparing the plan or evaluating a round.
  const busy =
    loop?.status === "planning" || loop?.rounds.some((r) => r.status === "completed") === true;
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [busy, load]);

  if (!loop) {
    return (
      <Page>
        <ErrorNote message={error} />
        {!error && <Spinner className="text-indigo-600" />}
      </Page>
    );
  }

  return (
    <Page>
      <h1 className="text-2xl font-semibold">{loop.title}</h1>
      <p className="mt-1 text-sm text-slate-500">
        {loop.mode === "company" ? "Company loop" : "Topic practice"} · {loop.level} level
      </p>
      {loop.disclaimer && <p className="mt-2 text-xs text-slate-500">{loop.disclaimer}</p>}
      {loop.research_sources.length > 0 && (
        <details className="mt-2 text-xs text-slate-500">
          <summary className="cursor-pointer">
            Interview style researched from {loop.research_sources.length} public candidate reports
          </summary>
          <ul className="mt-1 list-inside list-disc">
            {loop.research_sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline">
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
        </details>
      )}

      {loop.status === "planning" && (
        <Card className="mt-6 flex items-center gap-3">
          <Spinner className="text-indigo-600" />
          <div>
            <p className="font-medium">Your interviewers are preparing</p>
            <p className="text-sm text-slate-600">
              {loop.mode === "company"
                ? `Researching how ${loop.company} interviews, reading your resume and the JD, and planning each round. This takes 1-2 minutes.`
                : "Planning your questions. This takes about a minute."}
            </p>
          </div>
        </Card>
      )}

      {loop.status === "failed" && (
        <Card className="mt-6">
          <p className="font-medium">We couldn&apos;t prepare this interview.</p>
          <Button className="mt-3" onClick={() => api.retryLoop(loop.id).then(setLoop)}>
            Try again
          </Button>
        </Card>
      )}

      {loop.gap_map && (
        <Card className="mt-6">
          <h2 className="font-semibold">Where the interviewers will focus</h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-emerald-700">Strengths the JD wants</p>
              <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
                {loop.gap_map.strengths.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-sm font-medium text-amber-700">Gaps to prepare</p>
              <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
                {loop.gap_map.gaps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      )}

      {loop.status === "ready" && (
        <div className="mt-6 space-y-3">
          {loop.rounds.map((r) => {
            const st = ROUND_STATUS_LABEL[r.status];
            const verdict = r.verdict ? VERDICT_LABEL[r.verdict] : null;
            return (
              <Card key={r.id} className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    Round {r.index + 1} · {ROUND_TYPE_LABEL[r.type] ?? r.type} · {r.duration_min} min
                  </p>
                  <p className="mt-1 font-medium">{r.title}</p>
                  <div className="mt-2 flex gap-2">
                    <Badge tone={st.tone}>{st.label}</Badge>
                    {r.overall_score !== null && <Badge tone="indigo">{r.overall_score}/100</Badge>}
                    {verdict && <Badge tone={verdict.tone}>{verdict.label}</Badge>}
                  </div>
                </div>
                {r.status === "pending" || r.status === "in_progress" ? (
                  <LinkButton href={`/rounds/${r.id}/interview`}>
                    {r.status === "pending" ? "Start round" : "Rejoin"}
                  </LinkButton>
                ) : (
                  <LinkButton href={`/rounds/${r.id}/report`} variant="secondary">
                    View report
                  </LinkButton>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </Page>
  );
}
