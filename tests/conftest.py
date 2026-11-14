"""Shared fixtures for the engine, state, and utility tests."""

import json

from pathlib import Path

import pytest

import src.rooms.lab_d2_002 as lab_module
import src.phase as phase_module
from src.engine import Engine
from src.utils.colors import Colors
from src.utils.shell import VirtualShell
from src.utils.shell import ServerShell
from src.state import State
from src.server_state import ServerState
import src.state as state_module
from database import Database

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class FakeSavesQuery:
    """Stand-in for :class:`src.models.save.SaveQuery`."""

    def __init__(self, model):
        self.model = model
        self.conditions = {}

    def where(self, **conditions):
        self.conditions.update(conditions)
        return self

    def _matches(self, row):
        return all(row.get(key) == value for key, value in self.conditions.items())

    def first(self):
        for row in self.model.rows:
            if self._matches(row):
                return dict(row)
        return None

    def all(self):
        return [dict(row) for row in self.model.rows if self._matches(row)]


class FakeSaves:
    """Stand-in for :class:`src.models.save.Save` that never touches SQLite."""

    def __init__(self):
        self.created = []
        self.rows = []

    def create(self, slot, user_id):
        self.created.append((slot, user_id))
        return len(self.created)

    def find(self):
        return FakeSavesQuery(self)


class FakeUserQuery:
    def __init__(self, users, **matches):
        self.users = users
        self.matches = matches

    def where(self, **matches):
        return FakeUserQuery(self.users, **matches)

    def first(self):
        for user in self.users:
            if all(user.get(key) == value for key, value in self.matches.items()):
                return user
        return None


class FakeUser:
    def __init__(self):
        self.users = []
        self.counter = 0
        self.raise_on_create = None

    def create(self, name):
        if self.raise_on_create:
            raise self.raise_on_create
        self.counter += 1
        user = {"id": self.counter, "name": name}
        self.users.append(user)
        return user["id"]

    def find(self):
        return FakeUserQuery(self.users)


class FakeScoreboard:
    def __init__(self):
        self.created = []
        self.entries = []

    def create(self, data):
        self.created.append(data)
        return len(self.created)

    def find(self):
        return self

    def all(self):
        return list(self.entries)


class DummyLangchain:
    def __init__(self, provider, model_name=None):
        self.provider = provider
        self.model_name = model_name
        self.calls = []

    def respond(self, user_input):
        self.calls.append(user_input)


def make_game_data():
    """Return a complete, isolated state payload based on the real static data."""
    data = json.loads((DATA_DIR / "default.json").read_text(encoding="utf-8"))
    data["workbench"]["required_parts"] = [
        item_id for item_id, meta in data["items"].items() if meta.get("is_assembly_part")
    ]
    data["player"].update(
        {
            "id": 1,
            "name": "tester",
            "current_room": "lobby",
            "inventory": [],
            "move": [],
            "forward": [],
        }
    )
    timestamp = "2026-01-01T00:00:00+00:00"
    data["session"]["timestamp"] = timestamp
    data["session"]["duration"] = {
        "last_write": timestamp,
        "value": "00:00:00",
        "pause": False,
    }
    data["session"]["phase"] = "EXPLORATION"
    data["session"]["phases"]["assembly"]["duration"] = {
        "last_write": None,
        "value": "00:00:00",
        "pause": False,
    }
    data["session"]["phases"]["chat"]["duration"] = {
        "last_write": None,
        "value": "00:00:00",
        "pause": False,
    }
    data["running"] = True
    data["enable_colors"] = False
    data["terminal_width"] = 80
    return data


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(state_module, "Save", FakeSaves)
    state = State()
    state.data = make_game_data()
    state.USER_STATE_PATH = tmp_path / "user.json"
    state.SAVE_DIR = tmp_path / "saves"
    state._saves = FakeSaves()
    state.render_room = None
    return state


@pytest.fixture
def engine(state, monkeypatch):
    monkeypatch.setattr(phase_module, "Langchain", DummyLangchain)
    monkeypatch.setattr(lab_module, "Scoreboard", FakeScoreboard)
    engine = Engine(color=Colors())
    engine.state = state
    engine.scoreboard = FakeScoreboard()
    engine.user = FakeUser()
    engine.outputs = []
    engine.out = lambda text="", end=None: engine.outputs.append(text)
    return engine


@pytest.fixture
def db_table_names():
    def _table_names(conn):
        return {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    return _table_names


@pytest.fixture
def shell():
    return VirtualShell(
        {
            "etc": {"hostname": "teacher-pc"},
            "home": {
                "teacher": {
                    "Documents": {
                        "grades.csv": "grades",
                        "notes.md": "notes",
                        ".hidden.txt": "hidden",
                    },
                    "Downloads": {"manual.txt": "manual"},
                    ".secret": {"super_secret_file.txt": "the key"},
                    ".bashrc": "export PS1='$ '",
                    "README.txt": "read me",
                    "my notes.txt": "spaced",
                }
            },
            "var": {"log": {"nixos.log": "log"}},
        }
    )


@pytest.fixture
def server_shell_state():
    """A fresh, isolated server-provisioning challenge state."""
    return ServerState(ServerState.default())


@pytest.fixture
def server_shell(server_shell_state):
    """A ServerShell bound to a fresh state, with injected I/O and editor."""
    lines = []
    return ServerShell(
        server_shell_state,
        read_line=lambda prompt="": "",
        write=lines.append,
        editor=lambda text: (True, text),
    )


@pytest.fixture
def db(tmp_path):
    """An isolated SQLite database with the schema applied in a temp dir."""
    return Database(tmp_path / "game.db")


