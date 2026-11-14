"""Tests for the character-level modal editor."""

from src.utils.editor import ModalEditor
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
    KEY_UP,
)


def run_editor(text, keys):
    written = []
    editor = ModalEditor(
        text,
        read_key=iter(keys).__next__,
        write=written.append,
    )
    saved, result = editor.run()
    return saved, result, "".join(written)


def test_typing_inserts_characters():
    saved, result, _ = run_editor("ab", ["c", "d", KEY_CTRL_S])
    assert saved is True
    assert result == "abcd"


def test_backspace_deletes_the_character_before_the_cursor():
    _, result, _ = run_editor("abc", [KEY_BACKSPACE, KEY_CTRL_S])
    assert result == "ab"


def test_arrow_keys_move_the_cursor():
    _, result, _ = run_editor("abc", [KEY_LEFT, "X", KEY_CTRL_S])
    assert result == "abXc"
    _, result, _ = run_editor("abc", [KEY_RIGHT, "X", KEY_CTRL_S])
    assert result == "abcX"


def test_enter_inserts_a_newline():
    _, result, _ = run_editor("ab", [KEY_ENTER, "c", KEY_CTRL_S])
    assert result == "ab\nc"


def test_home_and_end_jump_to_the_line_edges():
    _, result, _ = run_editor("abc", [KEY_HOME, "X", KEY_CTRL_S])
    assert result == "Xabc"
    _, result, _ = run_editor("abc", [KEY_END, "X", KEY_CTRL_S])
    assert result == "abcX"


def test_down_moves_to_the_next_line():
    _, result, _ = run_editor(
        "ab\ncd", [KEY_HOME, KEY_UP, KEY_DOWN, "X", KEY_CTRL_S]
    )
    assert result == "ab\nXcd"


def test_up_moves_to_the_previous_line():
    _, result, _ = run_editor("ab\ncd", [KEY_HOME, KEY_UP, "X", KEY_CTRL_S])
    assert result == "Xab\ncd"


def test_backspace_at_the_line_start_joins_the_previous_line():
    _, result, _ = run_editor("ab\ncd", [KEY_HOME, KEY_BACKSPACE, KEY_CTRL_S])
    assert result == "abcd"


def test_ctrl_s_saves_the_edited_buffer():
    saved, result, _ = run_editor("ab", ["c", KEY_CTRL_S])
    assert saved is True
    assert result == "abc"


def test_ctrl_x_discards_the_edits():
    saved, result, _ = run_editor("ab", ["c", KEY_CTRL_X])
    assert saved is False
    assert result == "ab"


def test_escape_discards_the_edits():
    saved, result, _ = run_editor("ab", ["c", KEY_ESC])
    assert saved is False
    assert result == "ab"


def test_editor_redraws_with_escape_sequences():
    _, _, written = run_editor("ab", ["c", KEY_CTRL_S])
    assert "\x1b[" in "".join(written)


def test_cursor_cannot_move_before_the_start_of_a_line():
    _, result, _ = run_editor("ab", [KEY_LEFT, KEY_LEFT, KEY_LEFT, "X", KEY_CTRL_S])
    assert result == "Xab"


def test_cursor_is_clamped_to_the_end_of_a_shorter_line():
    _, result, _ = run_editor(
        "abcdef\nxy", [KEY_END, KEY_UP, KEY_END, KEY_DOWN, "X", KEY_CTRL_S]
    )
    assert result == "abcdef\nxyX"


def test_delete_removes_the_character_at_the_cursor():
    _, result, _ = run_editor("abc", [KEY_LEFT, KEY_DELETE, "S", KEY_CTRL_S])
    assert result == "abS"


def test_the_cursor_opens_at_the_end_of_the_buffer():
    _, result, _ = run_editor("ab\ncd", ["X", KEY_CTRL_S])
    assert result == "ab\ncdX"
