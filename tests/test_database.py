"""Tests for the sqlite :class:`database.Database` base."""

import sqlite3

import pytest

from database import Database


def test_creates_tables_idempotently(tmp_path):
    path = tmp_path / "game.db"
    Database(path)
    db = Database(path)  # second construction must not raise

    with db.connection() as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"users", "saves", "scoreboard"} <= names


def test_enforces_foreign_keys(tmp_path):
    db = Database(tmp_path / "game.db")
    with db.connection() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connection_commits_on_success(tmp_path):
    db = Database(tmp_path / "game.db")
    with db.connection() as conn:
        conn.execute("INSERT INTO users (name) VALUES ('alice')")

    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_connection_rolls_back_on_error(tmp_path):
    db = Database(tmp_path / "game.db")
    with pytest.raises(RuntimeError):
        with db.connection() as conn:
            conn.execute("INSERT INTO users (name) VALUES ('bob')")
            raise RuntimeError("boom")

    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_connection_closes_after_the_blocks_exits(tmp_path):
    db = Database(tmp_path / "game.db")
    with db.connection() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
