/** Runs the candidate's Python in a Web Worker (Pyodide), with a time limit. */

import { vendorUrl } from "../vendor";
import type { RunResult } from "./types";

const RUN_LIMIT_MS = 10_000; // for the candidate's code only
const LOAD_LIMIT_MS = 120_000; // first load downloads ~13 MB; allow slow connections

// Module worker (required by Pyodide): loads Pyodide once, reports "ready", then runs each
// snippet in a fresh namespace.
const WORKER_SOURCE = (base: string) => `
import { loadPyodide } from "${base}/pyodide.mjs";
const ready = loadPyodide({ indexURL: "${base}/" });
ready.then(() => postMessage({ ready: true }), (err) => postMessage({ ready: false, error: String(err) }));
onmessage = async (e) => {
  const py = await ready;
  const out = [];
  py.setStdout({ batched: (s) => out.push(s) });
  py.setStderr({ batched: (s) => out.push(s) });
  const ns = py.globals.get("dict")();
  try {
    await py.runPythonAsync(e.data.code, { globals: ns });
    postMessage({ ok: true, text: out.join("\\n") });
  } catch (err) {
    const msg = String(err && err.message ? err.message : err);
    // Keep the useful tail of Python tracebacks.
    postMessage({ ok: false, text: out.join("\\n"), error: msg.trim().split("\\n").slice(-4).join("\\n") });
  } finally {
    ns.destroy();
  }
};
`;

interface PyWorker {
  worker: Worker;
  ready: Promise<void>;
}

let current: PyWorker | null = null;

function getWorker(): PyWorker {
  if (!current) {
    const src = WORKER_SOURCE(vendorUrl("pyodide"));
    const worker = new Worker(URL.createObjectURL(new Blob([src], { type: "text/javascript" })), {
      type: "module",
    });
    const ready = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Python took too long to load. Check your connection and try again.")), LOAD_LIMIT_MS);
      worker.onmessage = (e: MessageEvent<{ ready?: boolean; error?: string }>) => {
        if (e.data.ready === undefined) return;
        clearTimeout(timer);
        if (e.data.ready) resolve();
        else reject(new Error(e.data.error || "Python failed to load"));
      };
      worker.onerror = (e) => {
        clearTimeout(timer);
        reject(new Error(e.message || "Python failed to load"));
      };
    });
    const entry = { worker, ready };
    ready.catch(() => {
      worker.terminate();
      if (current === entry) current = null;
    });
    current = entry;
  }
  return current;
}

/** Load Pyodide in the background so the first Run is fast. */
export function warmUpPython() {
  getWorker().ready.catch(() => undefined);
}

export async function runPython(code: string): Promise<RunResult> {
  const entry = getWorker();
  try {
    await entry.ready;
  } catch (e) {
    return { ok: false, text: "", error: e instanceof Error ? e.message : String(e), ms: 0 };
  }
  const started = performance.now();
  const { worker } = entry;
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      // Infinite loops etc.: kill the worker; the next run starts a fresh one.
      worker.terminate();
      if (current === entry) current = null;
      resolve({ ok: false, text: "", error: `Stopped after ${RUN_LIMIT_MS / 1000}s (possible infinite loop).`, ms: RUN_LIMIT_MS });
    }, RUN_LIMIT_MS);
    worker.onmessage = (e: MessageEvent<{ ok: boolean; text: string; error?: string }>) => {
      clearTimeout(timer);
      resolve({ ...e.data, text: e.data.text || (e.data.ok ? "(no output)" : ""), ms: performance.now() - started });
    };
    worker.onerror = (e) => {
      clearTimeout(timer);
      resolve({ ok: false, text: "", error: e.message || "Python crashed", ms: performance.now() - started });
    };
    worker.postMessage({ code });
  });
}
