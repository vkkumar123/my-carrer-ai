"use client";

import { loader } from "@monaco-editor/react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import { runPython, warmUpPython } from "@/lib/runners/python";
import { runSql } from "@/lib/runners/sql";
import type { RunResult } from "@/lib/runners/types";
import { vendorUrl } from "@/lib/vendor";

// Serve the editor ourselves (see scripts/copy-vendor.mjs), not from a public CDN.
loader.config({ paths: { vs: vendorUrl("monaco/vs") } });

const Monaco = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="p-4 text-sm text-slate-400">Loading editor...</div>,
});

export const LANGUAGES = ["sql", "python", "java", "cpp", "javascript", "typescript", "go", "scala"];
const RUNNABLE = new Set(["sql", "python"]);

/** Shared editor with Run (SQL and Python). Code and run output stream to the interviewer. */
export function CodeEditor({
  language,
  onLanguageChange,
  setupSql,
  onChange,
  onRun,
  onPasteBlocked,
}: {
  language: string;
  onLanguageChange: (language: string) => void;
  /** Sample tables for the current SQL question. */
  setupSql: string;
  onChange: (code: string, language: string) => void;
  onRun: (result: RunResult, language: string) => void;
  onPasteBlocked: () => void;
}) {
  const [code, setCode] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const runRef = useRef<(source?: string) => void>(() => {});

  useEffect(() => {
    const t = setTimeout(() => onChange(code, language), 1200);
    return () => clearTimeout(t);
  }, [code, language, onChange]);

  useEffect(() => {
    if (language === "python") warmUpPython();
  }, [language]);

  // `source` lets the keyboard shortcut pass the editor's live text, which can be newer than
  // the last rendered `code` state.
  const run = useCallback(async (source: string = code) => {
    if (!RUNNABLE.has(language) || running || !source.trim()) return;
    setRunning(true);
    try {
      const r = language === "sql" ? await runSql(setupSql, source) : await runPython(source);
      setResult(r);
      onRun(r, language);
    } catch (e) {
      const r = { ok: false, text: "", error: e instanceof Error ? e.message : String(e), ms: 0 };
      setResult(r);
      onRun(r, language);
    } finally {
      setRunning(false);
    }
  }, [code, language, onRun, running, setupSql]);
  useEffect(() => {
    runRef.current = run;
  }, [run]);

  // Capture-phase listeners run before Monaco's own handlers.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const block = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      onPasteBlocked();
    };
    el.addEventListener("paste", block, true);
    el.addEventListener("drop", block, true);
    return () => {
      el.removeEventListener("paste", block, true);
      el.removeEventListener("drop", block, true);
    };
  }, [onPasteBlocked]);

  const runnable = RUNNABLE.has(language);

  return (
    <div className="flex h-full flex-col bg-[#1e1e1e]">
      <div className="flex items-center justify-between gap-2 border-b border-slate-700 px-3 py-1.5">
        <span className="truncate text-xs text-slate-400">Your interviewer sees this live · paste disabled</span>
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-200"
          >
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
          <button
            onClick={() => run()}
            disabled={!runnable || running}
            title={runnable ? "Run (Ctrl/Cmd + Enter)" : "Run is available for SQL and Python"}
            className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            {running ? (language === "python" ? "Running (first run loads Python)..." : "Running...") : "▶ Run"}
          </button>
        </div>
      </div>
      <div ref={boxRef} className="min-h-0 flex-1">
        <Monaco
          theme="vs-dark"
          language={language}
          value={code}
          onChange={(v) => setCode(v ?? "")}
          onMount={(editor, monaco) => {
            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current(editor.getValue()));
          }}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            scrollBeyondLastLine: false,
            quickSuggestions: false,
            suggestOnTriggerCharacters: false,
            wordBasedSuggestions: "off",
            parameterHints: { enabled: false },
          }}
        />
      </div>
      {result && (
        <div className="max-h-[40%] shrink-0 overflow-auto border-t border-slate-700 bg-slate-950 p-3 font-mono text-xs">
          <p className={`mb-2 font-sans text-[11px] ${result.ok ? "text-emerald-400" : "text-rose-400"}`}>
            {result.ok ? "Ran successfully" : "Error"} · {Math.round(result.ms)} ms
            {result.truncated ? " · showing first 200 rows" : ""}
          </p>
          {result.error && <pre className="whitespace-pre-wrap text-rose-300">{result.error}</pre>}
          {result.columns && result.columns.length > 0 ? (
            <table className="border-collapse text-slate-200">
              <thead>
                <tr>
                  {result.columns.map((c) => (
                    <th key={c} className="border border-slate-700 px-2 py-1 text-left text-slate-400">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows!.map((r, i) => (
                  <tr key={i}>
                    {r.map((v, j) => (
                      <td key={j} className={`border border-slate-800 px-2 py-1 ${v === "NULL" ? "text-slate-500" : ""}`}>
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            result.text && <pre className="whitespace-pre-wrap text-slate-200">{result.text}</pre>
          )}
        </div>
      )}
    </div>
  );
}
