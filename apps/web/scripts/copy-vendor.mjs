// Copies browser runtimes from node_modules into public/vendor so the app serves them itself
// instead of depending on a third-party CDN (often blocked on office/college networks).
// Runs before `dev` and `build`; public/vendor is git-ignored.
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const nm = join(root, "node_modules");
const out = join(root, "public", "vendor");

const jobs = [
  // Code editor (AMD build used by @monaco-editor/react's loader)
  { from: "monaco-editor/min/vs", to: "monaco/vs" },
  // Face detection runtime (SIMD build; every supported browser has WebAssembly SIMD)
  { from: "@mediapipe/tasks-vision/wasm", to: "mediapipe", filter: (f) => f.startsWith("vision_wasm_internal.") },
  // Python in the browser
  { from: "pyodide", to: "pyodide", filter: (f) => /\.(js|mjs|wasm|zip|json)$/.test(f) && f !== "package.json" },
  // SQL in the browser: the "eh" build, which Chrome, Edge and Firefox all support
  {
    from: "@duckdb/duckdb-wasm/dist",
    to: "duckdb",
    filter: (f) => f === "duckdb-eh.wasm" || f === "duckdb-browser-eh.worker.js",
  },
];

// Plain per-file copies: Node's native recursive cpSync fails on some Docker bind mounts
// (e.g. Docker Desktop on macOS) with EACCES.
function copyDir(src, dest, filter) {
  mkdirSync(dest, { recursive: true });
  for (const name of readdirSync(src)) {
    const from = join(src, name);
    const to = join(dest, name);
    if (statSync(from).isDirectory()) {
      if (!filter) copyDir(from, to);
    } else if (!filter || filter(name)) {
      copyFileSync(from, to);
    }
  }
}

// Empty the folder rather than deleting it: in Docker it is a mounted volume.
mkdirSync(out, { recursive: true });
for (const name of readdirSync(out)) rmSync(join(out, name), { recursive: true, force: true });

for (const { from, to, filter } of jobs) {
  const src = join(nm, from);
  if (!existsSync(src)) throw new Error(`copy-vendor: missing ${src}; run npm install`);
  copyDir(src, join(out, to), filter);
}
console.log("copy-vendor: runtimes copied to public/vendor");
