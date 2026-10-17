"""Pure comparison helpers for DB-Pulse schema drift snapshots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

_SENSITIVE_COLUMN = re.compile(r"password|passwd|secret|token|credential|private.?key|connection.?string|database.?url|\bdsn\b", re.IGNORECASE)
_SENSITIVE_DEFAULT = re.compile(r"(?:password|passwd|secret|token)\s*=|://[^/:\s]+:[^@/\s]+@", re.IGNORECASE)


def index_columns(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """Convert information_schema column rows into a stable table/column map."""
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        table = str(row["TABLE_NAME"])
        column = str(row["COLUMN_NAME"])
        default_value = row.get("COLUMN_DEFAULT")
        default_text = str(default_value) if default_value is not None else ""
        redact_default = default_value is not None and (
            _SENSITIVE_COLUMN.search(column) is not None
            or _SENSITIVE_DEFAULT.search(default_text) is not None
        )
        indexed.setdefault(table, {})[column] = {
            "data_type": row.get("COLUMN_TYPE") or row.get("DATA_TYPE"),
            "nullable": str(row.get("IS_NULLABLE", "")).upper() == "YES",
            "default": "[REDACTED]" if redact_default else default_value,
            "default_redacted": redact_default,
            "primary_key": str(row.get("COLUMN_KEY", "")).upper() == "PRI",
            "ordinal_position": row.get("ORDINAL_POSITION"),
        }
    return indexed


def compare_schema(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic added, removed, and changed table/column differences."""
    before = {str(table): dict(columns) for table, columns in baseline.items()}
    after = {str(table): dict(columns) for table, columns in current.items()}
    added_tables = sorted(after.keys() - before.keys())
    removed_tables = sorted(before.keys() - after.keys())
    added_columns = []
    removed_columns = []
    changed_columns = []

    for table in sorted(before.keys() & after.keys()):
        old_columns, new_columns = before[table], after[table]
        for column in sorted(new_columns.keys() - old_columns.keys()):
            added_columns.append({"table": table, "column": column, "current": new_columns[column]})
        for column in sorted(old_columns.keys() - new_columns.keys()):
            removed_columns.append({"table": table, "column": column, "baseline": old_columns[column]})
        for column in sorted(old_columns.keys() & new_columns.keys()):
            old, new = old_columns[column], new_columns[column]
            if old != new:
                changed_columns.append({
                    "table": table,
                    "column": column,
                    "baseline": old,
                    "current": new,
                    "changed_fields": sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key)),
                })

    return {
        "added_tables": added_tables,
        "removed_tables": removed_tables,
        "added_columns": added_columns,
        "removed_columns": removed_columns,
        "changed_columns": changed_columns,
        "unchanged": not any((added_tables, removed_tables, added_columns, removed_columns, changed_columns)),
    }
