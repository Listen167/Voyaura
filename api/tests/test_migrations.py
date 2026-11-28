"""Execute the real Alembic chain on temporary databases, not create_all."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]


def migrate(database: Path, revision: str) -> None:
    env = {**os.environ, "VOYAURA_DATABASE_URL": "sqlite:///" + database.as_posix()}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=API,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("start", [None, "0014_agent_workflows", "0014_itinerary_contracts"])
def test_real_migration_chain_reaches_single_head(tmp_path: Path, start: str | None) -> None:
    database = tmp_path / "empty.db"
    if start:
        migrate(database, start)
    migrate(database, "head")
    with sqlite3.connect(database) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"users", "city_memories", "media_assets", "agent_runs", "agent_artifacts", "trips"} <= tables
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0015_merge_itinerary_agent"
        )
        assert db.execute("SELECT COUNT(*) FROM city_visits").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM city_memories").fetchone()[0] == 0


def test_historical_rows_survive_sqlite_batch_migrations(tmp_path: Path) -> None:
    database = tmp_path / "history.db"
    migrate(database, "0002_city_memories")
    with sqlite3.connect(database) as db:
        db.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("1" * 32, "test_migration", "Fixture only", None, "traveler", 1, None, "2026-01-01"),
        )
        db.execute(
            "INSERT INTO cities VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("2" * 32, "440100", "Guangzhou", "Guangzhou", "Guangdong", 113.26, 23.13),
        )
        db.execute(
            "INSERT INTO city_visits VALUES (?, ?, ?, ?, ?, ?)",
            ("3" * 32, "1" * 32, "2" * 32, "2026-01-01", "2026-01-01", None),
        )
        db.execute(
            "INSERT INTO city_memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "4" * 32,
                "1" * 32,
                "2" * 32,
                "fixture title",
                "preserve this text",
                "2026-01-01",
                "private",
                "2026-01-01",
                "2026-01-01",
            ),
        )
        db.execute(
            "INSERT INTO media_assets "
            "(id,memory_id,kind,storage_key,original_filename,mime_type,byte_size,created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "5" * 32,
                "4" * 32,
                "photo",
                "fixture/photo.jpg",
                "fixture.jpg",
                "image/jpeg",
                123,
                "2026-01-01",
            ),
        )
    migrate(database, "head")
    with sqlite3.connect(database) as db:
        row = db.execute("SELECT title, body, visibility FROM city_memories").fetchone()
        assert row == ("fixture title", "preserve this text", "private")
        assert db.execute("SELECT check_in_source FROM city_visits").fetchone()[0] == "device"
        assert db.execute(
            "SELECT storage_key,upload_status,scan_status FROM media_assets"
        ).fetchone() == ("fixture/photo.jpg", "ready", "not_scanned")
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
