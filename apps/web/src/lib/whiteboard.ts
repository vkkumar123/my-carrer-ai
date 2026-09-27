/**
 * Turns an Excalidraw scene into a short text description the interviewer (an LLM) can read:
 * labelled shapes, arrows between them, free text, and a count of freehand strokes.
 * Much cheaper and faster than sending screenshots, and it captures what matters in a design.
 */

/** The subset of Excalidraw element fields the summary needs. */
export interface BoardElement {
  id: string;
  type: string;
  isDeleted?: boolean;
  text?: string;
  containerId?: string | null;
  startBinding?: { elementId: string } | null;
  endBinding?: { elementId: string } | null;
  x: number;
  y: number;
}

const SHAPES = new Set(["rectangle", "ellipse", "diamond", "frame", "image", "embeddable"]);
const CONNECTORS = new Set(["arrow", "line"]);

const clean = (s: string) => s.replace(/\s+/g, " ").trim();

export function summarizeBoard(elements: readonly BoardElement[]): string {
  const live = elements.filter((e) => !e.isDeleted);
  if (live.length === 0) return "";

  const labels = new Map<string, string>();
  for (const e of live) {
    if (e.type === "text" && e.containerId && e.text) labels.set(e.containerId, clean(e.text));
  }

  // Top-to-bottom, left-to-right, the way people read a diagram.
  const shapes = live.filter((e) => SHAPES.has(e.type)).sort((a, b) => a.y - b.y || a.x - b.x);
  const names = new Map<string, string>();
  shapes.forEach((s, i) => names.set(s.id, labels.get(s.id) ? `"${labels.get(s.id)}"` : `unlabelled ${s.type} #${i + 1}`));

  const lines: string[] = [];
  if (shapes.length) {
    lines.push("Shapes:");
    for (const s of shapes) lines.push(`- ${s.type}: ${names.get(s.id)}`);
  }

  const connectors = live.filter((e) => CONNECTORS.has(e.type));
  if (connectors.length) {
    lines.push("Connections:");
    for (const c of connectors) {
      const from = c.startBinding ? names.get(c.startBinding.elementId) : undefined;
      const to = c.endBinding ? names.get(c.endBinding.elementId) : undefined;
      const label = labels.get(c.id);
      const arrow = c.type === "arrow" ? "->" : "--";
      lines.push(`- ${from ?? "(loose end)"} ${arrow} ${to ?? "(loose end)"}${label ? ` [${label}]` : ""}`);
    }
  }

  const notes = live
    .filter((e) => e.type === "text" && !e.containerId && e.text?.trim())
    .sort((a, b) => a.y - b.y || a.x - b.x);
  if (notes.length) {
    lines.push("Text notes:");
    for (const n of notes) lines.push(`- "${clean(n.text!)}"`);
  }

  const strokes = live.filter((e) => e.type === "freedraw").length;
  if (strokes) lines.push(`Freehand strokes: ${strokes} (not readable as text)`);

  return lines.join("\n").slice(0, 15000);
}
