"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Page } from "@/components/Nav";
import { Badge, Card, ErrorNote, LinkButton, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import type { Loop } from "@/lib/types";

function progress(loop: Loop) {
  const done = loop.rounds.filter((r) => r.status === "evaluated").length;
  const scores = loop.rounds.map((r) => r.overall_score).filter((s): s is number => s !== null);
  const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
  return { done, avg };
}

export default function Dashboard() {
  const ready = useRequireAuth();
  const [loops, setLoops] = useState<Loop[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    api.listLoops().then(setLoops, (e) => setError(e.message));
  }, [ready]);

  return (
    <Page>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Your interviews</h1>
        <LinkButton href="/new">New interview</LinkButton>
      </div>
      <div className="mt-6 space-y-3">
        <ErrorNote message={error} />
        {loops === null && !error && <Spinner className="text-indigo-600" />}
        {loops?.length === 0 && (
          <Card>
            <p className="font-medium">No interviews yet.</p>
            <p className="mt-1 text-sm text-slate-600">
              Start with a quick topic round (e.g. &quot;Apache Spark&quot;) or set up a full company
              loop with your resume and the job description.
            </p>
          </Card>
        )}
        {loops?.map((loop) => {
          const { done, avg } = progress(loop);
          return (
            <Link key={loop.id} href={`/loops/${loop.id}`} className="block">
              <Card className="transition hover:ring-indigo-300">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">{loop.title}</p>
                    <p className="text-sm text-slate-500">
                      {loop.mode === "company" ? "Company loop" : "Topic practice"} · {loop.level} ·{" "}
                      {formatDate(loop.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {loop.status === "planning" && <Badge tone="indigo">Preparing</Badge>}
                    {loop.status === "failed" && <Badge tone="red">Setup failed</Badge>}
                    {loop.status === "ready" && (
                      <Badge>
                        {done}/{loop.rounds.length} rounds done
                      </Badge>
                    )}
                    {avg !== null && <Badge tone="green">Avg {avg}/100</Badge>}
                  </div>
                </div>
              </Card>
            </Link>
          );
        })}
      </div>
    </Page>
  );
}
