export interface RunResult {
  ok: boolean;
  /** Tabular results (SQL). */
  columns?: string[];
  rows?: string[][];
  truncated?: boolean;
  /** Plain-text output: stdout for Python, a text table for SQL. */
  text: string;
  error?: string;
  ms: number;
}
