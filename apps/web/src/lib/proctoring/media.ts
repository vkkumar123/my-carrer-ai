/** Browser media helpers for the pre-interview checks. */

export function browserSupport(): { ok: boolean; reason?: string } {
  if (typeof navigator === "undefined") return { ok: false, reason: "Not running in a browser." };
  if (/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)) {
    return { ok: false, reason: "Interviews need a laptop or desktop: phones can't share the screen." };
  }
  if (!navigator.mediaDevices?.getDisplayMedia || !navigator.mediaDevices?.getUserMedia) {
    return { ok: false, reason: "This browser can't share your screen. Please use Chrome or Edge." };
  }
  return { ok: true };
}

export async function requestCamera(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
    audio: false,
  });
}

export async function requestMic(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
    video: false,
  });
}

export class ScreenShareError extends Error {}

/** Asks for a screen share and insists it is the *entire* screen, not a tab or window. */
export async function requestEntireScreen(): Promise<MediaStream> {
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: { displaySurface: "monitor" },
    audio: false,
    // Chrome-specific hints: prefer whole screens, hide the "share this tab" shortcut.
    monitorTypeSurfaces: "include",
    selfBrowserSurface: "exclude",
    surfaceSwitching: "exclude",
  } as DisplayMediaStreamOptions);
  const track = stream.getVideoTracks()[0];
  const surface = track?.getSettings().displaySurface;
  if (surface !== "monitor") {
    stream.getTracks().forEach((t) => t.stop());
    throw new ScreenShareError(
      surface
        ? "Please share your ENTIRE screen, not a single window or tab."
        : "Your browser doesn't report what you shared. Please use Chrome or Edge.",
    );
  }
  return stream;
}

/** True when a second monitor is connected (Chrome/Edge only; undefined elsewhere). */
export function hasExtraDisplay(): boolean | undefined {
  const s = window.screen as Screen & { isExtended?: boolean };
  return s.isExtended;
}

export function stopStream(stream: MediaStream | null | undefined) {
  stream?.getTracks().forEach((t) => t.stop());
}

/** Calls onLevel with a 0..1 loudness value ~10x a second. Returns a cleanup function. */
export function watchMicLevel(stream: MediaStream, onLevel: (v: number) => void): () => void {
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);
  const data = new Uint8Array(analyser.fftSize);
  const timer = setInterval(() => {
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (const v of data) sum += ((v - 128) / 128) ** 2;
    onLevel(Math.min(1, Math.sqrt(sum / data.length) * 4));
  }, 100);
  return () => {
    clearInterval(timer);
    source.disconnect();
    void ctx.close();
  };
}
