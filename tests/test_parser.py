"""Tests for the command parser."""

import pytest

from src.parser import Parser


@pytest.fixture
def parser():
    return Parser()


def test_normalize_room_key(parser):
    assert parser.normalize_room_key("  Lab_D2_001 ") == "lab d2 001"
    assert parser.normalize_room_key("Teachers   Room 1") == "teachers room 1"


def test_resolve_room_target(parser):
    assert parser.resolve_room_target("n") == "north"
    assert parser.resolve_room_target("lobby") == "lobby"
    assert parser.resolve_room_target("teacher room 4") == "teachers_room_4"
    assert parser.resolve_room_target("unknown place") == "unknown_place"


@pytest.mark.parametrize(
    ("raw", "verb"),
    [
        ("", "EMPTY"),
        ("   ", "EMPTY"),
        ("look", "look"),
        ("l", "look"),
        ("clear", "look"),
        ("inventory", "inventory"),
        ("inv", "inventory"),
        ("help", "help"),
        ("scoreboard", "scoreboard"),
        ("high score", "scoreboard"),
        ("status", "status"),
        ("check status", "status"),
        ("logout", "logout"),
        ("saves", "saves"),
        ("restart", "restart"),
        ("new game", "restart"),
        ("quit", "quit"),
        ("exit", "quit"),
        ("activate", "activate"),
        ("power", "activate"),
        ("add save slot", "save"),
        ("unknown-command", "UNKNOWN"),
        ("n", "go"),
        ("south", "go"),
        ("lobby", "go"),
        ("tr4", "go"),
        ("go north", "go"),
        ("move west", "go"),
        ("inspect desk", "inspect"),
        ("examine Blueprint", "inspect"),
        ("take battery pack", "take"),
        ("pick up battery pack", "take"),
        ("drop battery pack", "drop"),
        ("use battery pack", "use"),
    ],
)
def test_parse_verbs(parser, raw, verb):
    parsed_verb, details = parser.parse(raw)
    assert parsed_verb == verb
    assert isinstance(details, dict)


def test_parse_go_details(parser):
    verb, details = parser.parse("go Teachers Room 4")
    assert verb == "go"
    assert details["target"] == "teachers_room_4"
    assert details["raw"] == "teachers room 4"


def test_parse_use_with_indirect(parser):
    verb, details = parser.parse("use esp32 on workbench")
    assert verb == "use"
    assert details == {
        "target": "development_board",
        "indirect": "workbench",
        "raw": "esp32 on workbench",
    }


def test_parse_register_generates_username(parser):
    verb, details = parser.parse("register")
    assert verb == "register"
    assert details["target"].startswith(
        ("Operator_", "Cyber_", "Null_", "Cipher_", "Agent_", "Ghost_", "Vector_", "Node_")
    )


def test_register_retries_when_username_is_taken(parser, monkeypatch):
    class FakeUser:
        def __init__(self, results):
            self.results = iter(results)

        def find(self):
            return self

        def where(self, **kwargs):
            return self

        def first(self):
            return next(self.results)

    parser.user = FakeUser([object(), None])

    class FakeRandom:
        def __init__(self):
            self.nums = iter([111, 222])

        def choice(self, seq):
            return seq[0]

        def randint(self, low, high):
            return next(self.nums)

    monkeypatch.setattr("src.parser.random", FakeRandom())

    verb, details = parser.parse("register")
    assert details["target"] == "Operator_Aegis_222"


@pytest.mark.parametrize(
    ("raw", "message_fragment"),
    [
        ("go", "Go where"),
        ("inspect", "Inspect what"),
        ("take", "Take what"),
        ("drop", "drop what"),
        ("use", "Use what"),
        ("login", "valid username"),
        ("load", "valid slot"),
    ],
)
def test_parse_invalid_arguments(parser, raw, message_fragment):
    verb, details = parser.parse(raw)
    assert verb == "INVALID"
    assert message_fragment in details["message"]


def test_parse_register_with_name(parser):
    verb, details = parser.parse("register alice")
    assert verb == "register"
    assert details["target"] == "alice"


def test_parse_login_and_load(parser):
    assert parser.parse("login alice")[0] == "login"
    assert parser.parse("login alice")[1]["target"] == "alice"
    assert parser.parse("load slot1")[0] == "load"
    assert parser.parse("load slot1")[1]["target"] == "slot1"
    assert parser.parse("save slot1")[1]["target"] == "slot1"
    assert parser.parse("save")[1]["target"] is None