"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Lobby, type LobbyResult } from "@/components/interview/Lobby";
import { LiveRoom } from "@/components/interview/LiveRoom";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { JoinInfo, Round } from "@/lib/types";

export default function InterviewPage() {
  const ready = useRequireAuth();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [round, setRound] = useState<Round | null>(null);
  const [session, setSession] = useState<(LobbyResult & { join: JoinInfo }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    api.getRound(id).then(
      (r) => {
        if (r.status !== "pending" && r.status !== "in_progress") router.replace(`/rounds/${id}/report`);
        else setRound(r);
      },
      (e) => setError(e.message),
    );
  }, [ready, id, router]);

  if (error) {
    return (
      <main className="mx-auto max-w-lg p-8">
        <ErrorNote message={error} />
      </main>
    );
  }
  if (!round) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <Spinner className="text-indigo-600" />
      </main>
    );
  }
  if (!session) {
    return (
      <Lobby
        round={round}
        onReady={async (devices) => {
          const join = await api.joinRound(round.id, devices.voice);
          setSession({ ...devices, join });
        }}
      />
    );
  }
  return (
    <LiveRoom
      join={session.join}
      camera={session.camera}
      screen={session.screen}
      onFinished={() => router.replace(`/rounds/${round.id}/report`)}
    />
  );
}
