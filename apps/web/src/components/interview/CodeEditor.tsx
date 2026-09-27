"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

const Monaco = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="p-4 text-sm text-slate-400">Loading editor...</div>,
});

const LANGUAGES = ["python", "java", "cpp", "javascript", "typescript", "go", "sql", "scala"];

/** Shared editor. Code is streamed to the interviewer (debounced); pasting is blocked. */
export function CodeEditor({
  onChange,
  onPasteBlocked,
}: {
  onChange: (code: string, language: string) => void;
  onPasteBlocked: () => void;
}) {
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setTimeout(() => onChange(code, language), 1200);
    return () => clearTimeout(t);
  }, [code, language, onChange]);

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

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl bg-[#1e1e1e] ring-1 ring-slate-700">
      <div className="flex items-center justify-between border-b border-slate-700 px-3 py-2">
        <span className="text-xs text-slate-400">Shared with your interviewer · paste disabled</span>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-200"
        >
          {LANGUAGES.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </div>
      <div ref={boxRef} className="min-h-0 flex-1">
        <Monaco
          theme="vs-dark"
          language={language}
          value={code}
          onChange={(v) => setCode(v ?? "")}
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
    </div>
  );
}
