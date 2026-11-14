"""Tests for :class:`src.state.State`."""

import json

from datetime import timedelta

import src.state as state_module

from src.server_state import ServerState
from src.state import State


def test_state_seeds_and_exposes_server_state(state):
    assert isinstance(state.server, ServerState)
    assert state.server.system["ip_address"] == "10.11.7.42"


def test_persist_writes_the_server_section(state):
    state.server.system["hostname"] = "maze-server.thuas.nl"
    state.persist()
    payload = json.loads(state.USER_STATE_PATH.read_text(encoding="utf-8"))
    assert payload["server"]["system"]["hostname"] == "maze-server.thuas.nl"


def test_load_restores_the_server_section(state):
    state.server.system["pkg_upgraded"] = True
    state.persist()
    reloaded = State()
    reloaded.USER_STATE_PATH = state.USER_STATE_PATH
    reloaded.data = json.loads(state.USER_STATE_PATH.read_text(encoding="utf-8"))
    reloaded.normalize_state()
    assert reloaded.server.system["pkg_upgraded"] is True


def test_normalize_backfills_the_new_flag_and_item(state):
    del state.data["flags"]["lab_server_provisioned"]
    del state.data["items"]["server_provisioning_certificate"]

    state.normalize_state()

    assert state.flags["lab_server_provisioned"] is False
    assert (
        state.items["server_provisioning_certificate"]["name"]
        == "Server Provisioning Certificate"
    )


def test_room_descriptions_are_unique_and_present(state):
    descriptions = [room.get("description") for room in state.rooms.values()]

    assert len(descriptions) == len(state.rooms)
    assert all(desc and desc.strip() for desc in descriptions)
    assert len(set(descriptions)) == len(descriptions), (
        "two rooms share the same copy-pasted description"
    )


def test_mapping_protocol_and_properties(state):
    state = state
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


def test_normalize_migrates_legacy_state(state):
    state = state
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
    assert state.flags["tr4_secret_key_copied"] is False
    assert state.rooms["teachers_room_4"]["interactables"]["computer"]


def test_normalize_accepts_partial_duration_dict(state):
    state = state
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


def test_persist_writes_state_and_static_data(state):
    state.persist()
    payload = json.loads(state.USER_STATE_PATH.read_text(encoding="utf-8"))
    assert "rooms" in payload
    assert "items" in payload
    assert payload["running"] is True
    assert payload["player"]["name"] == "tester"
    assert payload["session"]["phase"] == "EXPLORATION"


def test_auto_advances_clock_and_persists(state, monkeypatch):
    monkeypatch.setattr(
        state_module, "calculate_duration", lambda start, end: timedelta(seconds=5)
    )
    state.session["duration"]["value"] = "00:00:10"

    state.auto()

    assert state.session["duration"]["value"] == "0:00:15"
    assert state.USER_STATE_PATH.exists()


def test_auto_paused_does_not_advance_or_persist(state, monkeypatch):
    monkeypatch.setattr(
        state_module, "calculate_duration", lambda start, end: timedelta(seconds=5)
    )
    state.session["duration"]["pause"] = True
    state.session["duration"]["value"] = "00:00:10"

    state.auto()

    assert state.session["duration"]["value"] == "00:00:10"
    assert state.session["phase"] == "EXPLORATION"
    assert not state.USER_STATE_PATH.exists()


def test_auto_switches_to_assembly_when_ready(state, monkeypatch):
    monkeypatch.setattr(
        state_module, "calculate_duration", lambda start, end: timedelta(seconds=0)
    )
    state.workbench["is_ready"] = True

    state.auto()

    assert state.session["phase"] == "ASSEMBLY"
    assert state.session["phases"]["assembly"]["activated"] is True
    assert state.session["phases"]["assembly"]["duration"]["last_write"]


def test_auto_advances_assembly_timer(state, monkeypatch):
    monkeypatch.setattr(
        state_module, "calculate_duration", lambda start, end: timedelta(minutes=1)
    )
    state.session["phase"] = "ASSEMBLY"
    state.session["phases"]["assembly"]["duration"]["last_write"] = (
        "2026-01-01T00:00:00+00:00"
    )

    state.auto()

    assert state.session["phases"]["assembly"]["duration"]["value"] == "0:01:00"


def test_save_requires_login(state):
    state.player["id"] = None

    ok, msg = state.save(None)

    assert not ok
    assert "registered" in msg


def test_save_creates_next_slot_and_sanitizes_names(state):
    state.save(None)
    assert state._saves.created == [("tester_save_slot_1", 1)]
    assert (state.SAVE_DIR / "tester_save_slot_1.json").exists()

    state.save(None)
    assert state._saves.created[-1] == ("tester_save_slot_2", 1)

    state.save({"target": "My Slot!"})
    assert state._saves.created[-1] == ("My_Slot", 1)
    assert (state.SAVE_DIR / "My_Slot.json").exists()


def test_save_refuses_existing_slot(state):
    state.save({"target": "slot"})

    ok, msg = state.save({"target": "slot"})

    assert not ok
    assert "unexpected error" in msg.lower()


def test_list_saves_reports_missing_login(state):
    state.player["id"] = None

    ok, message = state.list_saves()

    assert not ok
    assert "register" in message


def test_list_saves_returns_rows(state):
    rows = [{"slot": "slot-one", "created_at": "2026-01-01T00:00:00Z", "user_id": 1}]
    state._saves.rows = rows

    ok, result = state.list_saves()

    assert ok
    assert result == rows


def test_list_saves_empty(state):
    ok, message = state.list_saves()

    assert not ok
    assert "no saved slot" in message


def test_load_requires_login_and_ownership(state):
    state.player["id"] = None
    ok, msg = state.load({"target": "slot"})
    assert not ok
    assert "register" in msg

    state.player["id"] = 1
    ok, msg = state.load({"target": "slot"})
    assert not ok
    assert "do not have any progress" in msg

    state._saves.rows = [{"slot": "slot", "user_id": 1}]
    ok, msg = state.load({"target": "slot"})
    assert not ok
    assert "no saved progress" in msg


def test_load_restores_save_and_static_data(state):
    state._saves.rows = [{"slot": "slot", "user_id": 1}]
    state.SAVE_DIR.mkdir(parents=True, exist_ok=True)
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
    (state.SAVE_DIR / "slot.json").write_text(json.dumps(payload), encoding="utf-8")

    ok, msg = state.load({"target": "slot.json"})

    assert ok
    assert "Game loaded" in msg
    assert state.player["name"] == "loaded"
    assert state.player["current_room"] == "teachers_room_1"
    assert "lobby" in state.rooms
    assert "secret_key" in state.items
    assert state.session["duration"]["last_write"]


def test_move_direction_and_room_name(state):
    ok, msg = state.move({"target": "south"})
    assert ok
    assert state.player["current_room"] == "teachers_room_1"
    assert state.player["move"] == ["lobby"]

    ok, msg = state.move({"target": "lobby"})
    assert ok
    assert state.player["current_room"] == "lobby"
    assert state.player["move"] == ["lobby", "teachers_room_1"]


def test_move_back_and_forward(state):
    state.move({"target": "south"})
    state.move({"target": "back"})
    assert state.player["current_room"] == "lobby"
    assert state.player["forward"] == ["teachers_room_1"]

    state.move({"target": "forward"})
    assert state.player["current_room"] == "teachers_room_1"


def test_move_reports_bad_destinations(state):
    ok, msg = state.move({"target": "nowhere"})
    assert not ok
    assert "cannot go to nowhere" in msg

    state.rooms["lobby"]["exits"]["up"] = "missing_room"
    ok, msg = state.move({"target": "missing_room"})
    assert not ok
    assert "Unknown destination" in msg


def test_move_enforces_locks(state):
    state.player["current_room"] = "classroom_d2_035"

    ok, msg = state.move({"target": "project_room_1"})
    assert not ok
    assert "locked" in msg.lower()
    assert state.player["current_room"] == "classroom_d2_035"

    state.player["inventory"].append("keycard_lvl1")
    ok, _ = state.move({"target": "project_room_1"})
    assert ok
    assert state.player["current_room"] == "project_room_1"


def test_move_requires_all_listed_items(state):
    state.rooms["vault"] = {
        "name": "Vault",
        "description": "Storage",
        "exits": {},
        "items": [],
        "restricted": True,
        "requires": ["red_led", "green_led"],
    }
    state.rooms["lobby"]["exits"]["up"] = "vault"

    state.player["inventory"] = ["red_led"]
    ok, msg = state.move({"target": "vault"})
    assert not ok
    assert "Red Light Emitting Diode" in msg
    assert "Green Light Emitting Diode" in msg
    assert state.player["current_room"] == "lobby"

    state.player["inventory"] = ["red_led", "green_led"]
    ok, _ = state.move({"target": "vault"})
    assert ok
    assert state.player["current_room"] == "vault"


def test_move_rejects_restricted_room_without_requirement(state):
    state.rooms["restricted"] = {
        "name": "Restricted",
        "description": "No entry",
        "exits": {},
        "items": [],
        "restricted": True,
    }
    state.rooms["lobby"]["exits"]["down"] = "restricted"

    ok, msg = state.move({"target": "restricted"})

    assert not ok
    assert "locked" in msg.lower()


def test_history_errors(state):
    ok, msg = state.move({"target": "back"})
    assert not ok
    assert "no previous room" in msg

    ok, msg = state.move({"target": "forward"})
    assert not ok
    assert "no forward room" in msg

    state.player["move"] = ["missing"]
    ok, msg = state.move({"target": "back"})
    assert not ok
    assert "Unknown destination" in msg

    state.player["forward"] = ["missing"]
    ok, msg = state.move({"target": "forward"})
    assert not ok
    assert "Unknown destination" in msg


def test_reset_reloads_default_and_static_data(state):
    state.player["name"] = "changed"
    state.session["phase"] = "CHAT"

    state.reset()

    assert state.player["name"] is None
    assert state.session["phase"] == "EXPLORATION"
    assert "rooms" in state.data
    assert "items" in state.data
    assert state.running is True