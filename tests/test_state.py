"""Tests for :class:`src.state.State`."""

import json

from datetime import timedelta

import src.state as state_oop


def test_mapping_protocol_and_properties(oop_state):
    state = oop_state
    assert state["player"] is state.player
    assert state.get("player") is state.player
    assert state.get("missing", "fallback") == "fallback"
    assert "player" in state
    assert "missing" not in state
    assert "player" in list(iter(state))
    assert "player" in state.keys()
    assert state.player in state.values()
    assert len(state) == len(state.data)

    state["extra"] = 1
    assert state["extra"] == 1

    state.running = False
    assert state.running is False
    assert state.data["running"] is False
    state.running = True

    state.terminal_width = 42
    assert state.terminal_width == 42
    state.enable_colors = True
    assert state.enable_colors is True

    state.clear()
    assert len(state) == 0
    state.update({"a": 1})
    assert state["a"] == 1


def test_normalize_migrates_legacy_state(oop_state):
    state = oop_state
    state.data = {
        "game_state": {
            "timestamp": "2025-01-01T00:00:00+00:00",
            "duration": "1:02:03",
            "phase": "EXPLORATION",
        },
        "player": {
            "current_room": "teacher_room_4",
            "move": ["teacher_room_4"],
            "forward": [],
        },
        "rooms": {
            "teacher_room_4": {
                "exits": {"east": "teacher_room_4"},
                "interactables": {},
            }
        },
        "previous_room": "teacher_room_4",
    }

    state.normalize_state()

    assert "game_state" not in state.data
    assert "teachers_room_4" in state.rooms
    assert "teacher_room_4" not in state.rooms
    assert state.rooms["teachers_room_4"]["exits"]["east"] == "teachers_room_4"
    assert state.player["current_room"] == "teachers_room_4"
    assert state.player["move"] == ["teachers_room_4"]
    assert state.data["previous_room"] == "teachers_room_4"
    assert state.session["duration"] == {
        "last_write": "2025-01-01T00:00:00+00:00",
        "value": "1:02:03",
        "pause": False,
    }
    assert state.items["secret_key"]["name"] == "Secret Key"
    assert state.flags["tr4_secret_key_copied"] is False
    assert state.rooms["teachers_room_4"]["interactables"]["computer"]


def test_normalize_accepts_partial_duration_dict(oop_state):
    state = oop_state
    state.data = {
        "session": {
            "timestamp": "2025-01-01T00:00:00+00:00",
            "duration": {"pause": True},
        },
        "items": {"secret_key": {}},
        "flags": {},
    }

    state.normalize_state()

    assert state.session["duration"] == {
        "last_write": "2025-01-01T00:00:00+00:00",
        "value": "00:00:00",
        "pause": True,
    }


def test_persist_writes_only_mutable_state(oop_state):
    oop_state.persist()
    payload = json.loads(oop_state.USER_STATE_PATH.read_text(encoding="utf-8"))
    assert "rooms" not in payload
    assert "items" not in payload
    assert payload["running"] is True
    assert payload["player"]["name"] == "tester"
    assert payload["session"]["phase"] == "EXPLORATION"


def test_auto_advances_clock_and_persists(oop_state, monkeypatch):
    monkeypatch.setattr(
        state_oop, "calculate_duration", lambda start, end: timedelta(seconds=5)
    )
    oop_state.session["duration"]["value"] = "00:00:10"

    oop_state.auto()

    assert oop_state.session["duration"]["value"] == "0:00:15"
    assert oop_state.USER_STATE_PATH.exists()


def test_auto_paused_does_not_advance_or_persist(oop_state, monkeypatch):
    monkeypatch.setattr(
        state_oop, "calculate_duration", lambda start, end: timedelta(seconds=5)
    )
    oop_state.session["duration"]["pause"] = True
    oop_state.session["duration"]["value"] = "00:00:10"

    oop_state.auto()

    assert oop_state.session["duration"]["value"] == "00:00:10"
    assert oop_state.session["phase"] == "EXPLORATION"
    assert not oop_state.USER_STATE_PATH.exists()


def test_auto_switches_to_assembly_when_ready(oop_state, monkeypatch):
    monkeypatch.setattr(
        state_oop, "calculate_duration", lambda start, end: timedelta(seconds=0)
    )
    oop_state.workbench["is_ready"] = True

    oop_state.auto()

    assert oop_state.session["phase"] == "ASSEMBLY"
    assert oop_state.session["phases"]["assembly"]["activated"] is True
    assert oop_state.session["phases"]["assembly"]["duration"]["last_write"]


def test_auto_advances_assembly_timer(oop_state, monkeypatch):
    monkeypatch.setattr(
        state_oop, "calculate_duration", lambda start, end: timedelta(minutes=1)
    )
    oop_state.session["phase"] = "ASSEMBLY"
    oop_state.session["phases"]["assembly"]["duration"]["last_write"] = (
        "2026-01-01T00:00:00+00:00"
    )

    oop_state.auto()

    assert oop_state.session["phases"]["assembly"]["duration"]["value"] == "0:01:00"


def test_save_requires_login(oop_state):
    oop_state.player["id"] = None

    ok, msg = oop_state.save(None)

    assert not ok
    assert "registered" in msg


def test_save_creates_next_slot_and_sanitizes_names(oop_state):
    oop_state.save(None)
    assert oop_state._saves.created == [("tester_save_slot_1", 1)]
    assert (oop_state.SAVE_DIR / "tester_save_slot_1.json").exists()

    oop_state.save(None)
    assert oop_state._saves.created[-1] == ("tester_save_slot_2", 1)

    oop_state.save({"target": "My Slot!"})
    assert oop_state._saves.created[-1] == ("My_Slot", 1)
    assert (oop_state.SAVE_DIR / "My_Slot.json").exists()


def test_save_refuses_existing_slot(oop_state):
    oop_state.save({"target": "slot"})

    ok, msg = oop_state.save({"target": "slot"})

    assert not ok
    assert "unexpected error" in msg.lower()


def test_list_saves_reports_missing_login(oop_state):
    oop_state.player["id"] = None

    ok, message = oop_state.list_saves()

    assert not ok
    assert "register" in message


def test_list_saves_returns_rows(oop_state):
    rows = [{"slot": "slot-one", "created_at": "2026-01-01T00:00:00Z", "user_id": 1}]
    oop_state._saves.rows = rows

    ok, result = oop_state.list_saves()

    assert ok
    assert result == rows


def test_list_saves_empty(oop_state):
    ok, message = oop_state.list_saves()

    assert not ok
    assert "no saved slot" in message


def test_load_requires_login_and_ownership(oop_state):
    oop_state.player["id"] = None
    ok, msg = oop_state.load({"target": "slot"})
    assert not ok
    assert "register" in msg

    oop_state.player["id"] = 1
    ok, msg = oop_state.load({"target": "slot"})
    assert not ok
    assert "do not have any progress" in msg

    oop_state._saves.rows = [{"slot": "slot", "user_id": 1}]
    ok, msg = oop_state.load({"target": "slot"})
    assert not ok
    assert "no saved progress" in msg


def test_load_restores_save_and_static_data(oop_state):
    oop_state._saves.rows = [{"slot": "slot", "user_id": 1}]
    oop_state.SAVE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "player": {
            "id": 1,
            "name": "loaded",
            "current_room": "teachers_room_1",
            "inventory": [],
            "move": [],
            "forward": [],
        },
        "workbench": {
            "required_parts": ["chassis_frame"],
            "installed_parts": [],
            "is_ready": False,
        },
        "flags": {},
        "session": {
            "phase": "EXPLORATION",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "duration": {"last_write": None, "value": "00:01:00", "pause": False},
            "phases": {
                "assembly": {"activated": False, "duration": {}},
                "chat": {"activated": False, "robot": {"name": "Fred"}},
            },
        },
    }
    (oop_state.SAVE_DIR / "slot.json").write_text(json.dumps(payload), encoding="utf-8")

    ok, msg = oop_state.load({"target": "slot.json"})

    assert ok
    assert "Game loaded" in msg
    assert oop_state.player["name"] == "loaded"
    assert oop_state.player["current_room"] == "teachers_room_1"
    assert "lobby" in oop_state.rooms
    assert "secret_key" in oop_state.items
    assert oop_state.session["duration"]["last_write"]


def test_move_direction_and_room_name(oop_state):
    ok, msg = oop_state.move({"target": "east"})
    assert ok
    assert oop_state.player["current_room"] == "teachers_room_1"
    assert oop_state.player["move"] == ["lobby"]

    ok, msg = oop_state.move({"target": "lobby"})
    assert ok
    assert oop_state.player["current_room"] == "lobby"
    assert oop_state.player["move"] == ["lobby", "teachers_room_1"]


def test_move_back_and_forward(oop_state):
    oop_state.move({"target": "east"})
    oop_state.move({"target": "back"})
    assert oop_state.player["current_room"] == "lobby"
    assert oop_state.player["forward"] == ["teachers_room_1"]

    oop_state.move({"target": "forward"})
    assert oop_state.player["current_room"] == "teachers_room_1"


def test_move_reports_bad_destinations(oop_state):
    ok, msg = oop_state.move({"target": "nowhere"})
    assert not ok
    assert "cannot go to nowhere" in msg

    oop_state.rooms["lobby"]["exits"]["up"] = "missing_room"
    ok, msg = oop_state.move({"target": "missing_room"})
    assert not ok
    assert "Unknown destination" in msg


def test_move_enforces_locks(oop_state):
    oop_state.player["current_room"] = "classroom_d_2035"

    ok, msg = oop_state.move({"target": "project_room_1"})
    assert not ok
    assert "locked" in msg.lower()
    assert oop_state.player["current_room"] == "classroom_d_2035"

    oop_state.player["inventory"].append("keycard_lvl1")
    ok, _ = oop_state.move({"target": "project_room_1"})
    assert ok
    assert oop_state.player["current_room"] == "project_room_1"


def test_move_rejects_restricted_room_without_requirement(oop_state):
    oop_state.rooms["restricted"] = {
        "name": "Restricted",
        "description": "No entry",
        "exits": {},
        "items": [],
        "restricted": True,
    }
    oop_state.rooms["lobby"]["exits"]["down"] = "restricted"

    ok, msg = oop_state.move({"target": "restricted"})

    assert not ok
    assert "locked" in msg.lower()


def test_history_errors(oop_state):
    ok, msg = oop_state.move({"target": "back"})
    assert not ok
    assert "no previous room" in msg

    ok, msg = oop_state.move({"target": "forward"})
    assert not ok
    assert "no forward room" in msg

    oop_state.player["move"] = ["missing"]
    ok, msg = oop_state.move({"target": "back"})
    assert not ok
    assert "Unknown destination" in msg

    oop_state.player["forward"] = ["missing"]
    ok, msg = oop_state.move({"target": "forward"})
    assert not ok
    assert "Unknown destination" in msg


def test_spawn_repairs_invalid_room(oop_state):
    oop_state.player["current_room"] = "missing"
    oop_state.session["timestamp"] = None

    room_id = oop_state.spawn()

    assert room_id in oop_state.rooms
    assert oop_state.player["current_room"] == room_id
    assert oop_state.session["timestamp"]


def test_reset_reloads_default_and_static_data(oop_state):
    oop_state.player["name"] = "changed"
    oop_state.session["phase"] = "CHAT"

    oop_state.reset()

    assert oop_state.player["name"] == "guest"
    assert oop_state.session["phase"] == "EXPLORATION"
    assert "rooms" in oop_state.data
    assert "items" in oop_state.data
    assert oop_state.running is True