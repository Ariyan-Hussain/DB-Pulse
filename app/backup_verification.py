"""Preflight-only backup inspection. No restore execution is implemented."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BackupPreflightSettings:
    directory: Path
    maximum_bytes: int
    timeout_seconds: int


def load_settings() -> BackupPreflightSettings:
    raw_dir = os.getenv("DB_PULSE_BACKUP_DIR")
    if not raw_dir:
        raise ValueError("DB_PULSE_BACKUP_DIR is not configured")
    try:
        maximum = int(os.getenv("DB_PULSE_BACKUP_MAX_BYTES", str(100 * 1024 * 1024)))
        timeout = int(os.getenv("DB_PULSE_BACKUP_TIMEOUT_SECONDS", "60"))
    except ValueError:
        raise ValueError("Backup size and timeout settings must be whole numbers") from None
    if not 1 <= maximum <= 10 * 1024 * 1024 * 1024:
        raise ValueError("DB_PULSE_BACKUP_MAX_BYTES must be between 1 byte and 10 GiB")
    if not 1 <= timeout <= 900:
        raise ValueError("DB_PULSE_BACKUP_TIMEOUT_SECONDS must be between 1 and 900")
    return BackupPreflightSettings(Path(raw_dir).expanduser().resolve(), maximum, timeout)


def preflight_backup(filename: str, settings: BackupPreflightSettings) -> dict[str, Any]:
    """Check an in-directory SQL dump without executing or parsing its statements."""
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise ValueError("Provide a backup filename only; directory paths are not accepted")
    if Path(filename).suffix.lower() != ".sql":
        raise ValueError("Only uncompressed .sql dump files are supported for preflight")
    root = settings.directory.resolve()
    if not root.is_dir():
        raise FileNotFoundError("Configured backup directory is unavailable")
    candidate = root / filename
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError("Backup file must remain inside the configured backup directory") from None
    if not resolved.is_file():
        raise ValueError("Backup path must name a regular file")
    size = resolved.stat().st_size
    if size <= 0:
        raise ValueError("Backup file is empty")
    if size > settings.maximum_bytes:
        raise ValueError("Backup exceeds DB_PULSE_BACKUP_MAX_BYTES")
    with resolved.open("rb") as handle:
        prefix = handle.read(min(size, 4096))
    if b"\x00" in prefix:
        raise ValueError("File does not look like a plain-text SQL dump")
    try:
        prefix.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("SQL dump preflight requires a UTF-8 text file") from None

    mysql_client = shutil.which("mysql")
    return {
        "status": "preflight_complete",
        "backup_filename": filename,
        "size_bytes": size,
        "maximum_size_bytes": settings.maximum_bytes,
        "file_type": "plain UTF-8 SQL text (basic check only)",
        "mysql_client_available": mysql_client is not None,
        "configured_timeout_seconds": settings.timeout_seconds,
        "preflight_passed": mysql_client is not None,
        "restore_implemented": False,
        "restore_performed": False,
        "message": "This endpoint only checks backup-file preconditions. It does not execute dump contents or restore a database.",
        "warning": "SQL dumps can contain dangerous statements. Treat the file as untrusted and use a strongly isolated sandbox with restricted credentials for any separate restore process.",
    }
