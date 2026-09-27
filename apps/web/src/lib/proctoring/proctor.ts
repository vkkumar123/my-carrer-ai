/**
 * Live proctoring during a round. Watches camera, screen share, focus, fullscreen and the
 * candidate's face, and reports events. Critical issues (screen share or camera lost, another
 * person on camera) put the interview "on hold" until resolved, then a `resumed` event fires.
 */

import type { FaceDetector } from "@mediapipe/tasks-vision";

import type { ProctorEvent, ProctorSeverity } from "../types";
import { FACE_RULES, loadFaceDetector, sampleFace } from "./face";
import { hasExtraDisplay } from "./media";

export type CriticalIssue = "screen_share_stopped" | "camera_off" | "multiple_faces";

export interface ProctorState {
  holds: CriticalIssue[];
  fullscreen: boolean;
  faceWarning: "no_face" | "looking_away" | null;
}

interface Options {
  camera: MediaStream;
  screen: MediaStream;
  video: HTMLVideoElement;
  onEvent: (e: ProctorEvent) => void;
  onState: (s: ProctorState) => void;
}

export class Proctor {
  private opts: Options;
  private holds = new Set<CriticalIssue>();
  private faceWarning: ProctorState["faceWarning"] = null;
  private counters = { noFace: 0, multi: 0, away: 0 };
  private cleanups: (() => void)[] = [];
  private detector: FaceDetector | null = null;
  private stopped = false;

  constructor(opts: Options) {
    this.opts = opts;
  }

  async start() {
    this.watchTrack(this.opts.camera.getVideoTracks()[0], "camera_off");
    this.watchScreen(this.opts.screen);

    this.listen(document, "visibilitychange", () => {
      if (document.visibilityState === "hidden") this.emit("tab_hidden", "warn");
    });
    this.listen(window, "blur", () => {
      // A hidden tab already produced tab_hidden; blur alone means another app took focus.
      if (document.visibilityState === "visible") this.emit("window_blur", "warn");
    });
    this.listen(document, "fullscreenchange", () => {
      if (!document.fullscreenElement) this.emit("fullscreen_exit", "warn");
      this.publishState();
    });
    const scr = window.screen as Screen & EventTarget;
    this.listen(scr, "change", () => {
      if (hasExtraDisplay()) this.emit("extra_display", "warn");
    });

    try {
      this.detector = await loadFaceDetector();
      const timer = setInterval(() => this.checkFace(), FACE_RULES.sampleMs);
      this.cleanups.push(() => clearInterval(timer));
    } catch {
      this.emit("no_face", "info", { reason: "face_detector_unavailable" });
    }
    this.publishState();
  }

  /** Candidate re-shared their screen after it dropped. */
  replaceScreen(screen: MediaStream) {
    this.opts.screen = screen;
    this.watchScreen(screen);
    this.clearHold("screen_share_stopped");
  }

  reportPaste() {
    this.emit("paste_blocked", "warn");
  }

  stop() {
    this.stopped = true;
    this.cleanups.forEach((c) => c());
    this.cleanups = [];
  }

  // ------------------------------------------------------------------ internals

  private checkFace() {
    if (!this.detector || this.stopped) return;
    const s = sampleFace(this.detector, this.opts.video);
    if (!s) return;
    const r = FACE_RULES;
    this.counters.noFace = s.faces === 0 ? this.counters.noFace + 1 : 0;
    this.counters.multi = s.faces > 1 ? this.counters.multi + 1 : 0;
    this.counters.away = s.yaw !== null && s.yaw > r.lookAwayYaw ? this.counters.away + 1 : 0;

    if (this.counters.multi === r.multiFaceSamples) this.setHold("multiple_faces", { faces: s.faces });
    if (s.faces === 1 && this.holds.has("multiple_faces")) this.clearHold("multiple_faces");

    let warning: ProctorState["faceWarning"] = null;
    if (this.counters.noFace >= r.noFaceSamples) warning = "no_face";
    else if (this.counters.away >= r.lookAwaySamples) warning = "looking_away";
    if (warning && warning !== this.faceWarning) this.emit(warning, "warn");
    if (warning !== this.faceWarning) {
      this.faceWarning = warning;
      this.publishState();
    }
  }

  private watchScreen(screen: MediaStream) {
    this.watchTrack(screen.getVideoTracks()[0], "screen_share_stopped");
  }

  private watchTrack(track: MediaStreamTrack | undefined, issue: CriticalIssue) {
    if (!track) {
      this.setHold(issue);
      return;
    }
    const onEnded = () => this.setHold(issue);
    const onMute = () => this.setHold(issue, { muted: true });
    const onUnmute = () => this.clearHold(issue);
    track.addEventListener("ended", onEnded);
    track.addEventListener("mute", onMute);
    track.addEventListener("unmute", onUnmute);
    this.cleanups.push(() => {
      track.removeEventListener("ended", onEnded);
      track.removeEventListener("mute", onMute);
      track.removeEventListener("unmute", onUnmute);
    });
  }

  private setHold(issue: CriticalIssue, detail?: Record<string, unknown>) {
    if (this.holds.has(issue)) return;
    this.holds.add(issue);
    this.emit(issue, "critical", detail);
    this.publishState();
  }

  private clearHold(issue: CriticalIssue) {
    if (!this.holds.delete(issue)) return;
    if (this.holds.size === 0) this.emit("resumed", "info");
    this.publishState();
  }

  private emit(type: string, severity: ProctorSeverity, detail?: Record<string, unknown>) {
    if (this.stopped) return;
    this.opts.onEvent({ type, severity, detail, at: new Date().toISOString() });
  }

  private publishState() {
    this.opts.onState({
      holds: [...this.holds],
      fullscreen: !!document.fullscreenElement,
      faceWarning: this.faceWarning,
    });
  }

  private listen(target: EventTarget, name: string, fn: EventListener) {
    target.addEventListener(name, fn);
    this.cleanups.push(() => target.removeEventListener(name, fn));
  }
}
