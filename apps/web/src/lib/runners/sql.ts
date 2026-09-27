/** Runs the candidate's SQL in the browser (DuckDB-wasm) against the question's sample tables. */

import type { AsyncDuckDB } from "@duckdb/duckdb-wasm";

import { vendorUrl } from "../vendor";
import { asText, formatValue } from "./format";
import type { RunResult } from "./types";

const MAX_ROWS = 200;
let dbPromise: Promise<AsyncDuckDB> | null = null;

function getDb(): Promise<AsyncDuckDB> {
  dbPromise ??= (async () => {
    const duckdb = await import("@duckdb/duckdb-wasm");
    const eh = { mainModule: vendorUrl("duckdb/duckdb-eh.wasm"), mainWorker: vendorUrl("duckdb/duckdb-browser-eh.worker.js") };
    // Every supported browser runs the "eh" build; it's listed as the fallback too.
    const bundle = await duckdb.selectBundle({ mvp: eh, eh });
    const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), new Worker(bundle.mainWorker!));
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    return db;
  })();
  dbPromise.catch(() => {
    dbPromise = null;
  });
  return dbPromise;
}

export async function runSql(setupSql: string, query: string): Promise<RunResult> {
  const started = performance.now();
  const db = await getDb();
  const conn = await db.connect();
  try {
    // Fresh schema every run, so earlier runs can't leave tables or views behind.
    await conn.query("DROP SCHEMA IF EXISTS candidate CASCADE; CREATE SCHEMA candidate; USE candidate;");
    if (setupSql.trim()) await conn.query(setupSql);
    const table = await conn.query(query);
    const fields = table.schema.fields;
    const columns = fields.map((f) => f.name);
    const rows = table
      .toArray()
      .slice(0, MAX_ROWS)
      .map((r: Record<string, unknown>) =>
        fields.map((f) => formatValue(r[f.name], { typeId: f.typeId, scale: (f.type as { scale?: number }).scale })),
      );
    return { ok: true, columns, rows, text: asText(columns, rows), ms: performance.now() - started, truncated: table.numRows > MAX_ROWS };
  } catch (e) {
    const error = e instanceof Error ? e.message.split("\n")[0] : String(e);
    return { ok: false, text: "", error, ms: performance.now() - started };
  } finally {
    await conn.close();
  }
}
