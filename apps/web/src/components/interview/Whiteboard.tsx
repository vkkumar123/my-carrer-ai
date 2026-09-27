"use client";

import "@excalidraw/excalidraw/index.css";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef } from "react";

import { summarizeBoard, type BoardElement } from "@/lib/whiteboard";

const Excalidraw = dynamic(async () => (await import("@excalidraw/excalidraw")).Excalidraw, {
  ssr: false,
  loading: () => <div className="p-4 text-sm text-slate-400">Loading whiteboard...</div>,
});

/** Shared whiteboard. A text summary of the drawing streams to the interviewer (debounced). */
export function Whiteboard({
  onSummary,
  onPasteBlocked,
}: {
  onSummary: (summary: string) => void;
  onPasteBlocked: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const last = useRef("");

  const onChange = useCallback(
    (elements: readonly BoardElement[]) => {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        const summary = summarizeBoard(elements);
        if (summary !== last.current) {
          last.current = summary;
          onSummary(summary);
        }
      }, 1200);
    },
    [onSummary],
  );

  useEffect(() => () => clearTimeout(timer.current), []);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const block = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      onPasteBlocked();
    };
    el.addEventListener("paste", block, true);
    return () => el.removeEventListener("paste", block, true);
  }, [onPasteBlocked]);

  return (
    <div ref={boxRef} className="h-full w-full">
      <Excalidraw
        theme="dark"
        onChange={(elements) => onChange(elements as readonly BoardElement[])}
        UIOptions={{
          canvasActions: {
            loadScene: false,
            saveToActiveFile: false,
            export: false,
            saveAsImage: false,
            toggleTheme: false,
          },
        }}
      />
    </div>
  );
}
