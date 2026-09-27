"use client";

import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  StartAudio,
  useRoomContext,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { RoomEvent } from "livekit-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { requestEntireScreen, stopStream } from "@/lib/proctoring/media";
import { Proctor, type ProctorState } from "@/lib/proctoring/proctor";
import type { JoinInfo, ProctorEvent, Round } from "@/lib/types";

import { CodeEditor, LANGUAGES } from "./CodeEditor";
import { Whiteboard } from "./Whiteboard";

interface ScreenQuestion {
  index: number;
  total: number;
  id: string;
  topic: string;
  prompt: string;
  screen_text: string;
  workspace: "code" | "whiteboard" | "none";
  language: string;
}

type Tab = "code" | "whiteboard";

const DESIGN_ROUNDS = new Set(["system_design"]);

const HOLD_TEXT: Record<string, string> = {
  screen_share_stopped: "Your screen share stopped. Share your entire screen again to continue.",
  camera_off: "Your camera is off. Turn it back on to continue.",
  multiple_faces: "More than one person is visible. The interview continues when only you are in frame.",
};

interface Props {
  join: JoinInfo;
  camera: MediaStream;
  screen: MediaStream;
  onFinished: () => void;
}

export function LiveRoom(props: Props) {
  return (
    <LiveKitRoom
      serverUrl={props.join.livekit_url}
      token={props.join.token}
      connect
      audio
      video={false}
      className="flex h-screen flex-col bg-slate-950 text-slate-100"
    >
      <RoomAudioRenderer />
      <Session {...props} />
    </LiveKitRoom>
  );
}

function useCountdown(round: Round) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const start = round.started_at ? new Date(round.started_at).getTime() : now;
  const left = Math.round((start + round.duration_min * 60_000 - now) / 1000);
  const abs = Math.abs(left);
  return { text: `${left < 0 ? "-" : ""}${Math.floor(abs / 60)}:${String(abs % 60).padStart(2, "0")}`, over: left < 0 };
}

function Session({ join, camera, screen, onFinished }: Props) {
  const room = useRoomContext();
  const round = join.round;
  const { state: agentState, audioTrack, agent } = useVoiceAssistant();
  const transcriptions = useTranscriptions();
  const clock = useCountdown(round);
  const videoRef = useRef<HTMLVideoElement>(null);
  const proctorRef = useRef<Proctor | null>(null);
  const queue = useRef<ProctorEvent[]>([]);
  const screenRef = useRef(screen);
  const agentSeen = useRef(false);
  const finished = useRef(false);
  const [pstate, setPstate] = useState<ProctorState>({ holds: [], fullscreen: true, faceWarning: null });
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState<ScreenQuestion | null>(null);
  const [tab, setTab] = useState<Tab>(DESIGN_ROUNDS.has(round.type) ? "whiteboard" : "code");
  const [language, setLanguage] = useState("sql");
  const [boardOpened, setBoardOpened] = useState(tab === "whiteboard");

  const send = useCallback(
    (topic: string, payload: unknown) => {
      if (room.state !== "connected") return;
      const data = new TextEncoder().encode(JSON.stringify(payload));
      room.localParticipant.publishData(data, { reliable: true, topic }).catch(() => undefined);
    },
    [room],
  );

  const flush = useCallback(() => {
    if (!queue.current.length) return;
    const batch = queue.current.splice(0, queue.current.length);
    api.sendProctorEvents(round.id, batch).catch(() => queue.current.unshift(...batch));
  }, [round.id]);

  const finish = useCallback(() => {
    if (finished.current) return;
    finished.current = true;
    proctorRef.current?.stop();
    flush();
    stopStream(camera);
    stopStream(screenRef.current);
    if (document.fullscreenElement) document.exitFullscreen().catch(() => undefined);
    room.disconnect();
    onFinished();
  }, [camera, flush, onFinished, room]);

  // Start proctoring once the self-view is attached.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.srcObject = camera;
    const proctor = new Proctor({
      camera,
      screen,
      video,
      onEvent: (e) => {
        queue.current.push(e);
        send("proctor", { type: e.type, severity: e.severity });
      },
      onState: setPstate,
    });
    proctorRef.current = proctor;
    void proctor.start();
    const t = setInterval(flush, 5000);
    return () => {
      clearInterval(t);
      proctor.stop();
    };
  }, [camera, screen, send, flush]);

  // The interviewer ends the round by leaving the room. When it (re)joins, ask it to
  // resend the active question in case we missed it.
  useEffect(() => {
    if (agent) {
      agentSeen.current = true;
      send("sync", {});
    } else if (agentSeen.current) finish();
  }, [agent, finish, send]);

  // The interviewer pushes the active question to the problem panel.
  useEffect(() => {
    const onData = (payload: Uint8Array, _p: unknown, _k: unknown, topic?: string) => {
      if (topic !== "question") return;
      try {
        const q = JSON.parse(new TextDecoder().decode(payload)) as ScreenQuestion;
        setQuestion(q);
        if (q.workspace === "whiteboard") {
          setTab("whiteboard");
          setBoardOpened(true);
        } else if (q.workspace === "code") {
          setTab("code");
          if (LANGUAGES.includes(q.language)) setLanguage(q.language);
        }
      } catch {
        /* ignore malformed messages */
      }
    };
    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room]);

  useEffect(() => {
    const onUnload = () => flush();
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, [flush]);

  const onCode = useCallback((code: string, lang: string) => send("code", { code, language: lang }), [send]);
  const onBoard = useCallback((summary: string) => send("whiteboard", { summary }), [send]);
  const onPaste = useCallback(() => proctorRef.current?.reportPaste(), []);

  async function reshare() {
    setError(null);
    try {
      const s = await requestEntireScreen();
      screenRef.current = s;
      proctorRef.current?.replaceScreen(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Screen share failed");
    }
  }

  const captions = useMemo(
    () =>
      transcriptions.slice(-6).map((t) => ({
        id: t.streamInfo.id,
        who: agent && t.participantInfo.identity === agent.identity ? "Interviewer" : "You",
        text: t.text,
      })),
    [transcriptions, agent],
  );

  const statusText =
    !agent || agentState === "connecting" || agentState === "initializing"
      ? "Your interviewer is joining..."
    : agentState === "speaking"
      ? "Interviewer is speaking"
      : agentState === "thinking"
        ? "Interviewer is thinking"
        : "Listening";

  return (
    <>
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <div>
          <p className="text-xs text-slate-400">Round {round.index + 1}</p>
          <p className="font-medium">{round.title}</p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="flex items-center gap-1.5 rounded-full bg-rose-500/15 px-2.5 py-1 text-rose-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-rose-400" /> Proctored
          </span>
          <span className={`font-mono tabular-nums ${clock.over ? "text-amber-400" : "text-slate-200"}`}>{clock.text}</span>
          <Button variant="danger" onClick={() => setConfirmEnd(true)}>
            End interview
          </Button>
        </div>
      </header>

      {!pstate.fullscreen && (
        <div className="flex items-center justify-center gap-3 bg-amber-500/15 px-4 py-2 text-sm text-amber-200">
          You left fullscreen. This is noted in your report.
          <button className="underline" onClick={() => document.documentElement.requestFullscreen().catch(() => undefined)}>
            Return to fullscreen
          </button>
        </div>
      )}
      {pstate.faceWarning && (
        <div className="bg-amber-500/15 px-4 py-2 text-center text-sm text-amber-200">
          {pstate.faceWarning === "no_face" ? "We can't see your face on camera." : "Please keep looking at your screen."}
        </div>
      )}

      <main className="grid min-h-0 flex-1 gap-4 p-4 lg:grid-cols-[320px_1fr]">
        <section className="flex min-h-0 flex-col gap-4">
          <div className="flex flex-col items-center justify-center rounded-2xl bg-slate-900 p-5 ring-1 ring-slate-800">
            <div className="h-20 w-full max-w-[220px]">
              <BarVisualizer state={agentState} track={audioTrack} barCount={7} className="h-full w-full" />
            </div>
            <p className="mt-3 text-sm text-slate-400">{statusText}</p>
            <StartAudio label="Click to enable interviewer audio" className="mt-3 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm" />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto rounded-2xl bg-slate-900 p-4 text-sm ring-1 ring-slate-800">
            {captions.length === 0 ? (
              <p className="text-slate-500">Live captions appear here.</p>
            ) : (
              captions.map((c) => (
                <p key={c.id} className="mb-2">
                  <span className={c.who === "You" ? "text-emerald-400" : "text-indigo-300"}>{c.who}: </span>
                  {c.text}
                </p>
              ))
            )}
          </div>
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="aspect-video w-full -scale-x-100 rounded-2xl object-cover ring-1 ring-slate-800"
          />
        </section>

        <section className="flex min-h-0 flex-col gap-3">
          <div className="max-h-[38%] shrink-0 overflow-y-auto rounded-2xl bg-slate-900 p-4 ring-1 ring-slate-800">
            {question ? (
              <>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                  Question {question.index + 1} of {question.total} · {question.topic}
                </p>
                <p className="mt-2 text-slate-100">{question.prompt}</p>
                {question.screen_text && (
                  <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-slate-950 p-3 font-mono text-sm text-slate-200">
                    {question.screen_text}
                  </pre>
                )}
              </>
            ) : (
              <p className="text-sm text-slate-500">The question will appear here when your interviewer asks it.</p>
            )}
          </div>

          <div className="flex min-h-[420px] flex-1 flex-col overflow-hidden rounded-2xl ring-1 ring-slate-700">
            <div className="flex gap-1 border-b border-slate-700 bg-slate-900 px-2 pt-2">
              {(["code", "whiteboard"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setTab(t);
                    if (t === "whiteboard") setBoardOpened(true);
                  }}
                  className={`rounded-t-lg px-4 py-1.5 text-sm ${
                    tab === t ? "bg-[#1e1e1e] text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {t === "code" ? "Code editor" : "Whiteboard"}
                </button>
              ))}
            </div>
            {/* Both stay mounted so switching tabs never loses work. */}
            <div className="relative min-h-0 flex-1">
              <div className={`absolute inset-0 ${tab === "code" ? "" : "invisible"}`}>
                <CodeEditor language={language} onLanguageChange={setLanguage} onChange={onCode} onPasteBlocked={onPaste} />
              </div>
              {boardOpened && (
                <div className={`absolute inset-0 ${tab === "whiteboard" ? "" : "invisible"}`}>
                  <Whiteboard onSummary={onBoard} onPasteBlocked={onPaste} />
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      {pstate.holds.length > 0 && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/90 p-4">
          <div className="max-w-md rounded-2xl bg-slate-900 p-6 text-center ring-1 ring-slate-700">
            <p className="text-lg font-semibold">Interview on hold</p>
            {pstate.holds.map((h) => (
              <p key={h} className="mt-2 text-sm text-slate-300">
                {HOLD_TEXT[h]}
              </p>
            ))}
            {pstate.holds.includes("screen_share_stopped") && (
              <Button className="mt-4" onClick={reshare}>
                Share entire screen again
              </Button>
            )}
            {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
          </div>
        </div>
      )}

      {confirmEnd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4">
          <div className="max-w-sm rounded-2xl bg-slate-900 p-6 ring-1 ring-slate-700">
            <p className="font-semibold">End the interview now?</p>
            <p className="mt-2 text-sm text-slate-400">
              You can&apos;t rejoin this round. Your report is generated from what was covered so far.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirmEnd(false)}>
                Continue interview
              </Button>
              <Button variant="danger" onClick={finish}>
                End interview
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
