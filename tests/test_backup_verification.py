import pytest

from app.backup_verification import BackupPreflightSettings, preflight_backup


def test_preflight_checks_sql_file_without_restore(tmp_path, monkeypatch):
    (tmp_path / "sample.sql").write_text("CREATE TABLE demo (id INT);", encoding="utf-8")
    monkeypatch.setattr("app.backup_verification.shutil.which", lambda _: "mysql.exe")
    result = preflight_backup("sample.sql", BackupPreflightSettings(tmp_path, 1024, 30))
    assert result["preflight_passed"] is True
    assert result["restore_performed"] is False
    assert result["restore_implemented"] is False


def test_preflight_rejects_paths_traversal_and_non_sql(tmp_path):
    settings = BackupPreflightSettings(tmp_path, 1024, 30)
    for filename in ("../outside.sql", "nested\\dump.sql", "dump.txt"):
        with pytest.raises(ValueError):
            preflight_backup(filename, settings)


def test_preflight_rejects_oversize_and_empty_file(tmp_path):
    (tmp_path / "large.sql").write_text("12345", encoding="utf-8")
    (tmp_path / "empty.sql").write_text("", encoding="utf-8")
    settings = BackupPreflightSettings(tmp_path, 4, 30)
    with pytest.raises(ValueError, match="exceeds"):
        preflight_backup("large.sql", settings)
    with pytest.raises(ValueError, match="empty"):
        preflight_backup("empty.sql", settings)


def test_preflight_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / "outside_db_pulse.sql"
    outside.write_text("SELECT 1;", encoding="utf-8")
    link = tmp_path / "escape.sql"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable in this Windows environment")
    with pytest.raises(ValueError, match="inside"):
        preflight_backup("escape.sql", BackupPreflightSettings(tmp_path, 1024, 30))


def test_preflight_reports_missing_mysql_tool_without_claiming_success(tmp_path, monkeypatch):
    (tmp_path / "sample.sql").write_text("SELECT 1;", encoding="utf-8")
    monkeypatch.setattr("app.backup_verification.shutil.which", lambda _: None)
    result = preflight_backup("sample.sql", BackupPreflightSettings(tmp_path, 1024, 30))
    assert result["mysql_client_available"] is False
    assert result["preflight_passed"] is False
    assert result["restore_performed"] is False


def test_preflight_rejects_binary_file(tmp_path):
    (tmp_path / "binary.sql").write_bytes(b"\x00\xff\x00")
    with pytest.raises(ValueError, match="plain-text"):
        preflight_backup("binary.sql", BackupPreflightSettings(tmp_path, 1024, 30))
