/** Formats DuckDB (Arrow) result values for display, e.g. DATE and DECIMAL columns. */

// Arrow type ids (apache-arrow `Type` enum) for the types that need special handling.
const DECIMAL = 7;
const DATE = 8;
const TIMESTAMP = 10;

export interface ColumnType {
  typeId: number;
  scale?: number;
}

export function formatValue(value: unknown, type: ColumnType): string {
  if (value === null || value === undefined) return "NULL";
  if (type.typeId === DATE && typeof value === "number") {
    return new Date(value).toISOString().slice(0, 10);
  }
  if (type.typeId === TIMESTAMP && typeof value === "number") {
    return new Date(value).toISOString().replace("T", " ").replace(/(\.000)?Z$/, "");
  }
  if (type.typeId === DECIMAL) {
    return scaleDecimal(String(value), type.scale ?? 0);
  }
  if (typeof value === "bigint") return value.toString();
  if (typeof value === "object") {
    const v = value as { toJSON?: () => unknown };
    try {
      return JSON.stringify(v.toJSON ? v.toJSON() : v, (_k, x) => (typeof x === "bigint" ? x.toString() : x));
    } catch {
      return String(value);
    }
  }
  return String(value);
}

/** "1250" with scale 2 -> "12.50"; "-5" with scale 2 -> "-0.05". */
export function scaleDecimal(unscaled: string, scale: number): string {
  if (scale <= 0 || !/^-?\d+$/.test(unscaled)) return unscaled;
  const negative = unscaled.startsWith("-");
  const digits = (negative ? unscaled.slice(1) : unscaled).padStart(scale + 1, "0");
  const whole = digits.slice(0, -scale);
  const frac = digits.slice(-scale);
  return `${negative ? "-" : ""}${whole}.${frac}`;
}

/** Plain-text table for the interviewer (first rows only). */
export function asText(columns: string[], rows: string[][], maxRows = 30): string {
  if (columns.length === 0) return "(statement ran; no rows returned)";
  const lines = [columns.join(" | "), ...rows.slice(0, maxRows).map((r) => r.join(" | "))];
  if (rows.length > maxRows) lines.push(`... ${rows.length - maxRows} more rows`);
  if (rows.length === 0) lines.push("(0 rows)");
  return lines.join("\n");
}
