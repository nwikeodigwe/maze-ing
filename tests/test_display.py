"""Tests for the display helpers."""

from types import SimpleNamespace

import builtins

import config

import src.utils.display as display


def make_display_state(enable_colors=False, width=40):
    return SimpleNamespace(
        enable_colors=enable_colors,
        terminal_width=width,
        player={"current_room": "lobby", "name": "tester"},
        session={
            "phase": "EXPLORATION",
            "duration": {"value": "00:00:00", "pause": False},
        },
        rooms={
            "lobby": {
                "name": "Lobby",
                "exits": {"north": "hall", "nowhere": "missing"},
                "items": ["part"],
                "interactables": {"terminal": "Terminal"},
            },
            "hall": {"name": "Hall"},
        },
        items={
            "part": {
                "name": "Part",
                "description": "A part",
                "is_assembly_part": True,
            }
        },
    )


def test_safe_transliterates_and_falls_back():
    assert display.safe("a─b•c→d") == "a-b*c->d"
    assert display.safe("plain") == "plain"
    assert display.safe("emoji \U0001f600") == "emoji ?"


def test_prompt(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda prompt: "  answer  ")
    assert display.prompt() == "answer"
    assert display.prompt("Name") == "answer"


def test_colorize_respects_setting(monkeypatch):
    monkeypatch.setattr(config, "state", make_display_state(enable_colors=False))
    assert display.colorize("text", "\033[31m") == "text"

    monkeypatch.setattr(config, "state", make_display_state(enable_colors=True))
    assert display.colorize("text", "\033[31m") == "\033[31mtext\033[0m"


def test_out_and_draw_line(monkeypatch, capsys):
    monkeypatch.setattr(config, "state", make_display_state(width=5))
    display.out("hello", end="")
    display.draw_line("-")
    captured = capsys.readouterr().out
    assert "hello" in captured
    assert "-----" in captured