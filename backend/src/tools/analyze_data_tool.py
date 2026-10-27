"""
analyze_data_tool – answer questions about uploaded CSV/XLSX using DuckDB.

Flow: load schema + 5 sample rows → generate/validate SELECT query → execute via DuckDB
→ return table artifact + short summary.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings
from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_SELECT_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_UNSAFE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|PRAGMA|ATTACH|VACUUM)\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> Optional[str]:
    """Return None if safe SELECT, else rejection reason."""
    sql_stripped = sql.strip().rstrip(";")
    if not _SELECT_PATTERN.match(sql_stripped):
        return "Only SELECT queries are permitted."
    if _UNSAFE_PATTERN.search(sql_stripped):
        return "Query contains forbidden modification keywords."
    return None


def list_datasets() -> List[Dict[str, Any]]:
    """Return a list of available dataset files in data/datasets/."""
    path = settings.datasets_path
    path.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("*.csv", "*.xlsx", "*.xls"):
        for f in path.glob(ext):
            files.append({"filename": f.name, "size_bytes": f.stat().st_size})
    return files


class AnalyzeDataTool(BaseTool):
    """Answer questions about an uploaded CSV or XLSX dataset using DuckDB."""

    name = "analyze_data"
    description = (
        "Analyze an uploaded CSV or XLSX dataset with SQL queries using DuckDB. "
        "Returns a data table artifact and summary answering the analytical question."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The analytical question to answer about the dataset.",
            },
            "filename": {
                "type": "string",
                "description": "Dataset filename (e.g., 'test_sales.csv'). If omitted or when referring to 'uploaded csv', the active uploaded dataset is automatically used.",
            },
            "sql": {
                "type": "string",
                "description": "Optional: a read-only SELECT SQL query. If omitted, one will be generated.",
            },
        },
        "required": ["question"],
    }
    category = "data"

    def __init__(self) -> None:
        self._last_artifact: Optional[Dict[str, Any]] = None

    def run(  # type: ignore[override]
        self,
        question: str,
        filename: Optional[str] = None,
        sql: Optional[str] = None,
        **_: Any,
    ) -> str:
        """Load dataset, execute SELECT query via DuckDB, return summary + table artifact."""
        self._last_artifact = None

        try:
            import duckdb  # noqa: PLC0415
        except ImportError:
            return "[Error] duckdb is not installed. Run: pip install duckdb"

        # ── Smart dataset filename resolution ─────────────────────────────
        datasets = list_datasets()
        if not datasets:
            return "[Error] No datasets found in workspace. Please upload a CSV or XLSX file using the 'Upload CSV / XLSX' button in the sidebar."

        target_file: Optional[Path] = None
        raw_name = (filename or "").strip()

        # 1. Exact match if provided
        if raw_name:
            exact_path = settings.datasets_path / raw_name
            if exact_path.exists():
                target_file = exact_path

        # 2. If missing, or generic name like 'uploaded.csv', 'my_uploaded.csv', 'dataset.csv', etc.
        if not target_file:
            generic_names = {
                "uploaded.csv", "uploaded", "my_uploaded.csv", "my uploaded csv",
                "my_csv.csv", "my_csv", "dataset.csv", "dataset", "data.csv",
                "file.csv", "csv", "the csv", "uploaded data",
            }
            lower_raw = raw_name.lower()
            for d in datasets:
                d_name = d["filename"]
                if lower_raw and (lower_raw == d_name.lower() or lower_raw in d_name.lower() or d_name.lower() in lower_raw):
                    target_file = settings.datasets_path / d_name
                    filename = d_name
                    break

            if not target_file and (not raw_name or lower_raw in generic_names or len(datasets) == 1):
                target_file = settings.datasets_path / datasets[0]["filename"]
                logger.info("Auto-resolved dataset '%s' to active file: '%s'", raw_name, datasets[0]["filename"])
                filename = datasets[0]["filename"]

        if not target_file or not target_file.exists():
            available = [f["filename"] for f in datasets]
            return (
                f"Dataset '{filename or raw_name}' not found. "
                f"Available datasets: {available}"
            )

        filepath = target_file

        suffix = filepath.suffix.lower()
        try:
            conn = duckdb.connect(":memory:")

            # Safe table registration
            table_name = "data_table"
            if suffix == ".csv":
                conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{filepath}')")
            elif suffix in (".xlsx", ".xls"):
                import pandas as pd  # noqa: PLC0415
                df = pd.read_excel(filepath)
                conn.register("df_temp", df)
                conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_temp")
            else:
                return f"[Error] Unsupported file format '{suffix}'. Supported: .csv, .xlsx, .xls"

            # 1. Introspect schema & 5 sample rows
            schema_info = conn.execute(f"DESCRIBE {table_name}").fetchall()
            schema_cols = [f"{r[0]} ({r[1]})" for r in schema_info]
            sample_df = conn.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchdf()

            # 2. Determine SQL query to execute
            query_to_run = sql
            if not query_to_run:
                # Ask model for a SELECT query
                try:
                    from src.llm import llm_client
                    prompt = (
                        f"You are a DuckDB SQL generator. Table name is '{table_name}'.\n"
                        f"Columns: {', '.join(schema_cols)}\n"
                        f"Sample rows:\n{sample_df.to_string(index=False)}\n\n"
                        f"User question: {question}\n\n"
                        f"Write exactly ONE read-only SELECT SQL query to answer this question. "
                        f"Do NOT include markdown formatting, explanations, or code blocks. Just the raw SQL."
                    )
                    resp = llm_client.chat(messages=[{"role": "user", "content": prompt}], tools=None)
                    raw_sql = (resp.choices[0].message.content or "").strip()
                    # Strip any markdown fences if present
                    raw_sql = re.sub(r"^```[a-zA-Z]*\n?", "", raw_sql)
                    raw_sql = re.sub(r"\n?```$", "", raw_sql).strip()
                    query_to_run = raw_sql
                except Exception as exc:
                    logger.warning("LLM SQL generation failed: %s; falling back to LIMIT 10", exc)
                    query_to_run = f"SELECT * FROM {table_name} LIMIT 10"

            # 3. Validate query
            err = _validate_sql(query_to_run)
            if err:
                return f"[Error] SQL query rejected: {err}"

            # Make sure it references table_name
            if table_name not in query_to_run and "read_csv_auto" not in query_to_run:
                query_to_run = f"SELECT * FROM ({query_to_run}) AS sub"

            logger.info("Executing DuckDB query: %s", query_to_run)
            res_df = conn.execute(query_to_run).fetchdf()

            columns = [str(c) for c in res_df.columns]
            rows_raw = res_df.head(50).values.tolist()
            rows = [[str(v) if v is not None else "" for v in r] for r in rows_raw]

            # 4. Generate table artifact: {columns:[], rows:[[]]}
            self._last_artifact = {
                "kind": "table",
                "data": {
                    "columns": columns,
                    "rows": rows,
                },
            }

            summary = f"SQL: {query_to_run}\nReturned {len(res_df)} rows, {len(columns)} columns."
            table_preview = res_df.head(10).to_string(index=False)
            return truncate(f"{summary}\n\n{table_preview}")

        except Exception as exc:
            logger.exception("DuckDB execution error: %s", exc)
            return f"[Tool error] analyze_data: {exc}"
