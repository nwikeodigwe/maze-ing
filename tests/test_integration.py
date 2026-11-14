"""End-to-end integration tests.

These tests exercise the actual ``Engine``, ``State``, ``Parser``, rooms and the
real SQLite models (``User``/``Save``/``Scoreboard``) wired to an isolated temp
database, rather than the fakes used by the unit tests. Only the genuinely
external seams are stubbed: the network-backed chat model (``Langchain``) and
non-deterministic timing (``time.sleep``).

The player is driven through ``Engine.run()`` with a scripted input sequence and
the resulting game state is asserted (not the exact terminal output).
"""

import pytest

from src.engine import Engine
from src.state import State
from src.models.save import Save
from src.models.scoreboard import Scoreboard
from src.models.user import User


class FakeLangchain:
    """Stub the network-backed chat model so no API calls happen in tests."""

    def __init__(self, provider="gemini", model_name=None):
        self.provider = provider
        self.model_name = model_name
        self.calls = []

    def respond(self, user_input):
        self.calls.append(user_input)


@pytest.fixture
def integration_engine(tmp_path, monkeypatch):
    """A fully isolated engine: real state, models and parser over a temp DB."""
    monkeypatch.setattr("src.phase.Langchain", FakeLangchain)
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    state = State()
    state._saves = Save(path=tmp_path / "game.db")
    state.USER_STATE_PATH = tmp_path / "user.json"
    state.SAVE_DIR = tmp_path / "saves"
    state.reset()

    engine = Engine()
    engine.state = state
    engine.user = User(path=tmp_path / "game.db")
    engine.scoreboard = Scoreboard(path=tmp_path / "game.db")
    engine.render_room = engine.render
    engine.outputs = []
    engine.out = lambda text="", end=None: engine.outputs.append(text)
    engine.clear = lambda: None
    return engine


def play(engine, commands, monkeypatch):
    """Run the engine until it stops, feeding ``commands`` one per prompt."""
    inputs = iter(commands)
    monkeypatch.setattr(engine, "prompt", lambda *args, **kwargs: next(inputs))
    engine.run()
    return engine


def test_register_creates_a_real_user_row(integration_engine, monkeypatch):
    play(integration_engine, ["go front_desk", "register alice", "quit"], monkeypatch)

    assert integration_engine.player["name"] == "alice"
    assert integration_engine.player["id"] is not None
    # The user is persisted to the real (temp) database, not a fake.
    row = integration_engine.user.find().where(name="alice").first()
    assert row is not None
    assert row["id"] == integration_engine.player["id"]


def test_register_requires_the_front_desk(integration_engine, monkeypatch):
    play(integration_engine, ["register alice", "quit"], monkeypatch)

    assert integration_engine.player["id"] is None
    assert integration_engine.user.find().where(name="alice").first() is None


def test_save_and_load_restore_progress(integration_engine, monkeypatch):
    play(
        integration_engine,
        [
            "go front_desk",
            "register alice",
            "go lobby",
            "take red_led",
            "save",
            "take oled_display",
            "load alice_save_slot_1",
            "quit",
        ],
        monkeypatch,
    )

    # The load restored the world as it was at save time.
    assert integration_engine.player["inventory"] == ["red_led"]
    assert integration_engine.player["current_room"] == "lobby"
    # And the save row exists in the real database.
    rows = integration_engine.state._saves.find().all()
    assert [row["slot"] for row in rows] == ["alice_save_slot_1"]


def test_restricted_room_blocks_without_the_required_item(integration_engine, monkeypatch):
    play(integration_engine, ["go north", "quit"], monkeypatch)

    # classroom_d2_015 requires development_board, which the player does not hold.
    assert integration_engine.player["current_room"] == "lobby"


def test_restricted_room_allows_after_taking_the_required_item(integration_engine, monkeypatch):
    play(integration_engine, ["take development_board", "go north", "quit"], monkeypatch)

    assert integration_engine.player["current_room"] == "classroom_d2_015"


def test_take_moves_an_item_from_room_to_inventory(integration_engine, monkeypatch):
    play(integration_engine, ["take oled_display", "quit"], monkeypatch)

    assert "oled_display" in integration_engine.player["inventory"]
    assert "oled_display" not in integration_engine.state.rooms["lobby"]["items"]


def test_full_exploration_session_runs_to_quit_without_error(integration_engine, monkeypatch):
    # A realistic freeform session through several rooms and commands.
    engine = play(
        integration_engine,
        [
            "look",
            "go front_desk",
            "register ada",
            "go lobby",
            "take development_board",
            "take oled_display",
            "inventory",
            "go north",
            "look",
            "quit",
        ],
        monkeypatch,
    )

    assert engine.player["name"] == "ada"
    assert engine.player["current_room"] == "classroom_d2_015"
    assert engine.state.running is False
