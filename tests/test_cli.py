"""Tests for the CLI commands using typer.testing."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner, Result

from pv.cli import app

runner = CliRunner()


def _invoke(*args: str, db: Path | None = None) -> Result:
    """Helper to invoke the CLI with a temp DB."""
    cmd = list(args)
    if db:
        cmd += ["--db", str(db)]
    result = runner.invoke(app, cmd)
    return result


class TestInit:
    def test_init_creates_db(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        result = _invoke("init", db=db)
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "✓" in result.output

    def test_init_creates_alembic_version(self, tmp_path: Path) -> None:
        import sqlite3

        db = tmp_path / "test.db"
        _invoke("init", db=db)
        conn = sqlite3.connect(str(db))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "alembic_version" in tables
        rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        assert len(rows) == 1
        conn.close()

    def test_init_idempotent(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        r1 = _invoke("init", db=db)
        r2 = _invoke("init", db=db)
        assert r1.exit_code == 0
        assert r2.exit_code == 0


class TestVersion:
    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "pv" in result.output
        assert "0.1.0" in result.output


class TestAdd:
    def test_add_version(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        result = _invoke("add", "my-prompt", "--content", "Hello!", db=db)
        assert result.exit_code == 0
        assert "v1" in result.output

    def test_add_from_file(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        f = tmp_path / "prompt.txt"
        f.write_text("File content here")
        result = _invoke("add", "fp", "--file", str(f), db=db)
        assert result.exit_code == 0

    def test_add_no_content_fails(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        result = _invoke("add", "p", db=db)
        assert result.exit_code == 1


class TestList:
    def test_list_empty(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        result = _invoke("list", db=db)
        assert result.exit_code == 0

    def test_list_with_prompts(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p1", "-c", "hello", db=db)
        _invoke("add", "p2", "-c", "world", db=db)
        result = _invoke("list", db=db)
        assert result.exit_code == 0

    def test_list_json(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p1", "-c", "hello", db=db)
        result = _invoke("list", "--json", db=db)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "p1"


class TestLog:
    def test_log(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "v1", db=db)
        _invoke("add", "p", "-c", "v2", db=db)
        result = _invoke("log", "p", db=db)
        assert result.exit_code == 0

    def test_log_json(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "v1", db=db)
        result = _invoke("log", "p", "--json", db=db)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestShow:
    def test_show_latest(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "latest content", db=db)
        result = _invoke("show", "p", db=db)
        assert result.exit_code == 0
        assert "latest content" in result.output

    def test_show_specific_version(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "v1-text", db=db)
        _invoke("add", "p", "-c", "v2-text", db=db)
        result = _invoke("show", "p", "--version", "1", db=db)
        assert result.exit_code == 0
        assert "v1-text" in result.output

    def test_show_json(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "content", db=db)
        result = _invoke("show", "p", "--json", db=db)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["content"] == "content"


class TestDiff:
    def test_diff(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "line1\nline2\n", db=db)
        _invoke("add", "p", "-c", "line1\nchanged\n", db=db)
        result = _invoke("diff", "p", "1", "2", db=db)
        assert result.exit_code == 0


class TestRollback:
    def test_rollback(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "original", db=db)
        _invoke("add", "p", "-c", "changed", db=db)
        result = _invoke("rollback", "p", "1", db=db)
        assert result.exit_code == 0
        assert "v3" in result.output


class TestTag:
    def test_add_tag(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "v1", db=db)
        result = _invoke("tag", "p", "1", "--add", "prod", db=db)
        assert result.exit_code == 0

    def test_no_tag_action_fails(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "v1", db=db)
        result = _invoke("tag", "p", "1", db=db)
        assert result.exit_code == 1


class TestExport:
    def test_export_stdout(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "hello", db=db)
        result = _invoke("export", "p", db=db)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "p"

    def test_export_to_file(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "hello", db=db)
        out = tmp_path / "out.json"
        result = _invoke("export", "p", "--output", str(out), db=db)
        assert result.exit_code == 0
        assert out.exists()


class TestDelete:
    def test_delete_with_yes(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _invoke("init", db=db)
        _invoke("add", "p", "-c", "v1", db=db)
        result = _invoke("delete", "p", "--yes", db=db)
        assert result.exit_code == 0
        assert "Deleted" in result.output or "✓" in result.output
