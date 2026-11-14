"""Tests for :class:`src.models.user.User` and :class:`UserQuery`."""

import sqlite3

import pytest

from src.models.user import User


def test_create_returns_autoincrement_id_and_sets_name(db):
    user = User(path=db.path)
    user_id = user.create("alice")

    assert isinstance(user_id, int)
    assert user.data["name"] == "alice"


def test_create_duplicate_name_raises(db):
    user = User(path=db.path)
    user.create("alice")

    with pytest.raises(sqlite3.IntegrityError):
        user.create("alice")


def test_create_without_name_raises_because_name_is_required(db):
    user = User(path=db.path)

    with pytest.raises(sqlite3.IntegrityError):
        user.create()


def test_find_by_name_hit_and_miss(db):
    user = User(path=db.path)
    alice_id = user.create("alice")
    user.create("bob")

    found = user.find().where(name="alice").first()
    assert found["id"] == alice_id
    assert found["name"] == "alice"

    assert user.find().where(name="nobody").first() is None


def test_find_first_without_conditions(db):
    user = User(path=db.path)
    user.create("alice")

    row = user.find().first()
    assert row["name"] == "alice"
