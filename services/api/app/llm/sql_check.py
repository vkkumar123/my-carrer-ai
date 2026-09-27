"""Makes sure the sample tables for SQL questions actually load (DuckDB, like the browser)."""

import duckdb


def setup_sql_error(setup_sql: str) -> str | None:
    """None when the script runs cleanly on an empty in-memory database, else the error."""
    if not setup_sql.strip():
        return None
    con = duckdb.connect(":memory:")
    try:
        con.execute(setup_sql)
        return None
    except duckdb.Error as e:
        return str(e).splitlines()[0][:300]
    finally:
        con.close()
