"use client";

import { useEffect, useRef, useState } from "react";

import { Button, Card, ErrorNote } from "@/components/ui";
import { FACE_RULES, loadFaceDetector, sampleFace } from "@/lib/proctoring/face";
import {
  browserSupport,
  hasExtraDisplay,
  requestCamera,
  requestEntireScreen,
  requestMic,
  stopStream,
  watchMicLevel,
} from "@/lib/proctoring/media";
import type { Round } from "@/lib/types";

export type Voice = "female" | "male";

export interface LobbyResult {
  camera: MediaStream;
  screen: MediaStream;
  voice: Voice;
}

const VOICE_OPTIONS: { value: Voice; label: string }[] = [
  { value: "female", label: "Priya (female voice)" },
  { value: "male", label: "Rahul (male voice)" },
];

type Check = "pending" | "ok" | "fail";

function Row({ status, title, children }: { status: Check; title: string; children?: React.ReactNode }) {
  const icon = status === "ok" ? "✓" : status === "fail" ? "!" : "·";
  const tone =
    status === "ok"
      ? "bg-emerald-100 text-emerald-700"
      : status === "fail"
        ? "bg-rose-100 text-rose-700"
        : "bg-slate-100 text-slate-500";
  return (
    <div className="flex gap-3 border-b border-slate-100 py-4 last:border-0">
      <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-sm font-bold ${tone}`}>
        {icon}
      </span>
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        <div className="mt-1 text-sm text-slate-600">{children}</div>
      </div>
    </div>
  );
}

export function Lobby({ round, onReady }: { round: Round; onReady: (r: LobbyResult) => Promise<void> }) {
  const support = browserSupport();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [camera, setCamera] = useState<MediaStream | null>(null);
  const [faces, setFaces] = useState<number | null>(null);
  const [micOk, setMicOk] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [micStream, setMicStream] = useState<MediaStream | null>(null);
  const [screen, setScreen] = useState<MediaStream | null>(null);
  const [extraDisplay, setExtraDisplay] = useState<boolean | undefined>(() => hasExtraDisplay());
  const [consent, setConsent] = useState(false);
  const [voice, setVoice] = useState<Voice>("female");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const handedOff = useRef(false);

  // Attach camera preview and run face detection while in the lobby.
  useEffect(() => {
    if (!camera || !videoRef.current) return;
    videoRef.current.srcObject = camera;
    let timer: ReturnType<typeof setInterval> | undefined;
    loadFaceDetector().then(
      (det) => {
        timer = setInterval(() => {
          const s = videoRef.current && sampleFace(det, videoRef.current);
          if (s) setFaces(s.faces);
        }, FACE_RULES.sampleMs / 2);
      },
      () => setError("Couldn't load face detection. Check your connection and reload."),
    );
    return () => clearInterval(timer);
  }, [camera]);

  // Mic level meter; one clear sound is enough to pass.
  useEffect(() => {
    if (!micStream) return;
    return watchMicLevel(micStream, (v) => {
      setMicLevel(v);
      if (v > 0.15) setMicOk(true);
    });
  }, [micStream]);

  // If the candidate stops sharing from the browser bar while still in the lobby.
  useEffect(() => {
    const track = screen?.getVideoTracks()[0];
    if (!track) return;
    const onEnded = () => setScreen(null);
    track.addEventListener("ended", onEnded);
    return () => track.removeEventListener("ended", onEnded);
  }, [screen]);

  // Release devices if the candidate leaves the lobby without starting.
  const streams = useRef<(MediaStream | null)[]>([]);
  useEffect(() => {
    streams.current = [camera, screen, micStream];
  }, [camera, screen, micStream]);
  useEffect(
    () => () => {
      const [cam, scr, mic] = streams.current;
      stopStream(mic);
      if (!handedOff.current) {
        stopStream(cam);
        stopStream(scr);
      }
    },
    [],
  );

  async function run(fn: () => Promise<void>) {
    setError(null);
    try {
      await fn();
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      setError(
        name === "NotAllowedError"
          ? "Permission was denied. Allow access in your browser's address bar and try again."
          : e instanceof Error
            ? e.message
            : "Something went wrong",
      );
    }
  }

  const cameraCheck: Check = !camera || faces === null ? "pending" : faces === 1 ? "ok" : "fail";
  const screenCheck: Check = screen ? "ok" : "pending";
  const displayCheck: Check = extraDisplay ? "fail" : "ok";
  const allOk =
    support.ok && cameraCheck === "ok" && micOk && screenCheck === "ok" && displayCheck === "ok" && consent;

  async function start() {
    if (!camera || !screen) return;
    setStarting(true);
    setError(null);
    try {
      await document.documentElement.requestFullscreen().catch(() => undefined);
      stopStream(micStream); // LiveKit opens its own mic track
      handedOff.current = true;
      await onReady({ camera, screen, voice });
    } catch (e) {
      handedOff.current = false;
      setError(e instanceof Error ? e.message : "Could not start the interview");
      setStarting(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-6 px-4 py-8 lg:grid-cols-[1fr_320px]">
      <Card>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Before you begin</p>
        <h1 className="mt-1 text-xl font-semibold">{round.title}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {round.duration_min} minutes, by voice. Like a real remote interview, your camera stays on
          and your entire screen is shared for the whole round.
        </p>

        <div className="mt-4">
          <Row status={support.ok ? "ok" : "fail"} title="Supported device">
            {support.ok ? "Desktop browser detected." : support.reason}
          </Row>

          <Row status={cameraCheck} title="Camera on, only you in frame">
            {!camera ? (
              <Button variant="secondary" onClick={() => run(async () => setCamera(await requestCamera()))}>
                Turn on camera
              </Button>
            ) : faces === null ? (
              "Checking..."
            ) : faces === 1 ? (
              "Face detected."
            ) : faces === 0 ? (
              "We can't see your face. Sit facing the camera in good light."
            ) : (
              "More than one person is visible. The interview must be taken alone."
            )}
          </Row>

          <Row status={micOk ? "ok" : "pending"} title="Microphone">
            {!micStream ? (
              <Button variant="secondary" onClick={() => run(async () => setMicStream(await requestMic()))}>
                Test microphone
              </Button>
            ) : (
              <div className="space-y-2">
                <p>{micOk ? "We can hear you." : "Say something, like \"Hello, can you hear me?\""}</p>
                <div className="h-2 w-48 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full bg-emerald-500 transition-all" style={{ width: `${micLevel * 100}%` }} />
                </div>
              </div>
            )}
          </Row>

          <Row status={screenCheck} title="Share your entire screen">
            {screen ? (
              "Entire screen is being shared."
            ) : (
              <div className="space-y-2">
                <p>In the browser dialog, choose the &quot;Entire screen&quot; tab. Windows or tabs aren&apos;t accepted.</p>
                <Button variant="secondary" onClick={() => run(async () => setScreen(await requestEntireScreen()))}>
                  Share entire screen
                </Button>
              </div>
            )}
          </Row>

          <Row status={displayCheck} title="Single display">
            {extraDisplay ? (
              <div className="space-y-2">
                <p>A second monitor is connected. Disconnect it, then re-check.</p>
                <Button variant="secondary" onClick={() => setExtraDisplay(hasExtraDisplay())}>
                  Re-check
                </Button>
              </div>
            ) : extraDisplay === false ? (
              "One display detected."
            ) : (
              "Your browser can't detect extra monitors. Please use a single display."
            )}
          </Row>

          <Row status="ok" title="Your interviewer">
            <div className="flex flex-wrap gap-2">
              {VOICE_OPTIONS.map((v) => (
                <button
                  key={v.value}
                  type="button"
                  onClick={() => setVoice(v.value)}
                  className={`rounded-lg px-3 py-1.5 text-sm ring-1 ${
                    voice === v.value ? "bg-indigo-50 text-indigo-800 ring-indigo-400" : "ring-slate-300 hover:bg-slate-50"
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
            <p className="mt-2">Indian English accent. You can answer in English, Hindi or both.</p>
          </Row>

          <Row status={consent ? "ok" : "pending"} title="Consent">
            <label className="flex items-start gap-2">
              <input type="checkbox" className="mt-1" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>
                I agree that during this round my voice is transcribed and my camera and screen are
                monitored for integrity. Camera and screen video is analysed on this device and is
                not recorded or uploaded; only integrity events (e.g. &quot;tab switched&quot;) are saved
                with my report.
              </span>
            </label>
          </Row>
        </div>

        <ErrorNote message={error} />
        <Button className="mt-4 w-full" disabled={!allOk || starting} onClick={start}>
          {starting ? "Connecting to your interviewer..." : "Enter fullscreen and start interview"}
        </Button>
      </Card>

      <div className="space-y-4">
        <div className="aspect-[4/3] overflow-hidden rounded-2xl bg-slate-900">
          <video ref={videoRef} autoPlay muted playsInline className="h-full w-full -scale-x-100 object-cover" />
        </div>
        <Card className="text-sm text-slate-600">
          <p className="font-medium text-slate-900">Tips</p>
          <ul className="mt-2 list-inside list-disc space-y-1">
            <li>Use headphones so the interviewer&apos;s voice isn&apos;t picked up by your mic.</li>
            <li>Think out loud: the interviewer grades your reasoning, not just the answer.</li>
            <li>It&apos;s fine to say &quot;let me think&quot; and take a moment.</li>
            <li>Switching tabs or leaving fullscreen is noticed, just like in a real interview.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
