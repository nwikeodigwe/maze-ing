"""Tests for cross-platform key reading."""

from src.utils.keys import (
    KEY_BACKSPACE,
    KEY_CTRL_S,
    KEY_CTRL_X,
    KEY_DELETE,
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_ESC,
    KEY_HOME,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
    read_key,
)


def test_literal_characters_pass_through():
    assert read_key(lambda: "a") == "a"
    assert read_key(lambda: "q") == "q"


def test_posix_escape_sequences_are_normalized():
    assert read_key(iter(["\x1b", "[", "A"]).__next__) == KEY_UP
    assert read_key(iter(["\x1b", "[", "B"]).__next__) == KEY_DOWN
    assert read_key(iter(["\x1b", "[", "C"]).__next__) == KEY_RIGHT
    assert read_key(iter(["\x1b", "[", "D"]).__next__) == KEY_LEFT
    assert read_key(iter(["\x1b", "[", "H"]).__next__) == KEY_HOME
    assert read_key(iter(["\x1b", "[", "F"]).__next__) == KEY_END
    assert read_key(iter(["\x1b", "[", "3", "~"]).__next__) == KEY_DELETE
    assert read_key(iter(["\x1b", "O", "H"]).__next__) == KEY_HOME
    assert read_key(iter(["\x1b", "O", "F"]).__next__) == KEY_END


def test_windows_prefix_sequences_are_normalized():
    assert read_key(iter(["\xe0", "H"]).__next__) == KEY_UP
    assert read_key(iter(["\xe0", "P"]).__next__) == KEY_DOWN
    assert read_key(iter(["\xe0", "K"]).__next__) == KEY_LEFT
    assert read_key(iter(["\xe0", "M"]).__next__) == KEY_RIGHT
    assert read_key(iter(["\xe0", "G"]).__next__) == KEY_HOME
    assert read_key(iter(["\xe0", "O"]).__next__) == KEY_END
    assert read_key(iter(["\xe0", "S"]).__next__) == KEY_DELETE


def test_control_characters_are_normalized():
    assert read_key(lambda: "\r") == KEY_ENTER
    assert read_key(lambda: "\n") == KEY_ENTER
    assert read_key(lambda: "\x08") == KEY_BACKSPACE
    assert read_key(lambda: "\x7f") == KEY_BACKSPACE
    assert read_key(lambda: "\t") == KEY_TAB
    assert read_key(lambda: "\x1b") == KEY_ESC
    assert read_key(lambda: "\x13") == KEY_CTRL_S
    assert read_key(lambda: "\x18") == KEY_CTRL_X
