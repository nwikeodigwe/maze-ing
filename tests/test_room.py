"""Tests for the shared ``Room`` rendering helpers."""

from types import SimpleNamespace

import builtins

import src.room as room_module


def make_state(enable_colors=False, width=40):
    """A minimal stand-in for the active ``State`` that the helpers read."""
    return SimpleNamespace(enable_colors=enable_colors, terminal_width=width)


def test_safe_transliterates_and_falls_back():
    room = room_module.Room(state=make_state())
    assert room.safe("a─b•c→d") == "a-b*c->d"
    assert room.safe("plain") == "plain"
    assert room.safe("emoji \U0001f600") == "emoji ?"


def test_prompt(monkeypatch):
    room = room_module.Room(state=make_state())
    monkeypatch.setattr(builtins, "input", lambda prompt=None: "  answer  ")
    assert room.prompt() == "answer"
    assert room.prompt("Name") == "answer"


def test_colorize_respects_setting():
    off = room_module.Room(state=make_state(enable_colors=False))
    assert off.colorize("text", "\033[31m") == "text"

    on = room_module.Room(state=make_state(enable_colors=True))
    assert on.colorize("text", "\033[31m") == "\033[31mtext" + on.color.RESET


def test_out_and_draw_line(capsys):
    room = room_module.Room(state=make_state(width=5))
    room.out("hello", end="")
    room.draw_line("-")
    captured = capsys.readouterr().out
    assert "hello" in captured
    assert "-----" in captured
