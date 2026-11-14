"""Tests for :class:`src.models.scoreboard.Scoreboard` and :class:`ScoreboardQuery`."""

from src.models.scoreboard import Scoreboard
from src.models.user import User


def _row(uid, score, exploration="00:01:00", assembly="00:00:00"):
    return {
        "user_id": uid,
        "score": score,
        "avg_room_time": "00:00:00",
        "exploration_time": exploration,
        "assembly_time": assembly,
    }


def test_create_inserts_row_and_returns_id(db):
    uid = User(path=db.path).create("alice")
    board = Scoreboard(path=db.path)

    row_id = board.create(_row(uid, 100))

    assert isinstance(row_id, int)


def test_all_sorts_by_score_desc_then_total_time(db):
    uid = User(path=db.path).create("alice")
    board = Scoreboard(path=db.path)

    # Inserted out of order on purpose.
    board.create(_row(uid, 10, "00:01:00", "00:00:00"))
    board.create(_row(uid, 20, "00:03:00", "00:00:00"))
    board.create(_row(uid, 20, "00:01:00", "00:00:00"))
    board.create(_row(uid, 30, "00:09:00", "00:00:00"))

    rows = board.find().all()

    assert [row["score"] for row in rows] == [30, 20, 20, 10]
    # Ties on score break toward the shorter exploration time.
    assert rows[1]["exploration_time"] == "00:01:00"
    assert rows[2]["exploration_time"] == "00:03:00"


def test_first_returns_none_when_empty(db):
    board = Scoreboard(path=db.path)

    assert board.find().first() is None


def test_first_with_condition(db):
    uid = User(path=db.path).create("alice")
    board = Scoreboard(path=db.path)
    board.create(_row(uid, 99))

    row = board.find().where(user_id=uid).first()
    assert row["score"] == 99
