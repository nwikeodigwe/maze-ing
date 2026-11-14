"""Tests for :class:`src.models.save.Save` and :class:`SaveQuery`."""

import sqlite3

import pytest

from src.models.save import Save
from src.models.user import User


def _create_user(db, name="alice"):
    user = User(path=db.path)
    return user.create(name)


def test_create_returns_id_and_records_owner(db):
    uid = _create_user(db)

    save = Save(path=db.path)
    save_id = save.create("slot_1", uid)

    assert isinstance(save_id, int)
    assert save.user["id"] == uid


def test_create_duplicate_slot_raises(db):
    uid = _create_user(db)
    save = Save(path=db.path)
    save.create("slot_1", uid)

    with pytest.raises(sqlite3.IntegrityError):
        save.create("slot_1", uid)


def test_create_uses_id_from_constructor_data(db):
    uid = _create_user(db)
    save = Save({"id": uid}, path=db.path)

    save.create("slot_2")

    assert save.find().where(slot="slot_2").first()["user_id"] == uid


def test_find_where_first_and_all(db):
    uid = _create_user(db)
    save = Save(path=db.path)
    save.create("slot_1", uid)
    save.create("slot_2", uid)
    save.create("slot_3", uid)

    assert save.find().where(slot="slot_2").first()["slot"] == "slot_2"
    assert save.find().where(slot="nope").first() is None

    slots = [row["slot"] for row in save.find().where(user_id=uid).all()]
    assert slots == ["slot_1", "slot_2", "slot_3"]


def test_all_orders_by_id(db):
    uid = _create_user(db)
    save = Save(path=db.path)
    save.create("a", uid)
    save.create("b", uid)
    save.create("c", uid)

    ids = [row["id"] for row in save.find().all()]
    assert ids == sorted(ids)
