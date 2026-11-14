"""A nano-style character-level modal editor with injected input and output.

The editor renders the file on screen, places the cursor inside the text, and
applies single-key edits the way nano does. Reading and writing are injected so
the editor can be driven by a scripted key list in tests.
"""

from __future__ import annotations

from collections.abc import Callable

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
    read_key as platform_read_key,
)

_CLEAR = "\x1b[H\x1b[2J"


class ModalEditor:
    """Edit a text buffer in place, one keystroke at a time.

    Attributes:
        title: Optional label shown above the text.
    """

    def __init__(
        self,
        text: str,
        read_key: Callable[[], str] | None = None,
        write: Callable[[str], None] | None = None,
        title: str = "",
    ) -> None:
        """Prepare an editor over ``text``.

        Args:
            text: The starting buffer contents.
            read_key: Callable returning one key token. Defaults to the
                platform's single-key reader.
            write: Callable receiving rendered output. Defaults to ``print``.
            title: Optional label shown above the text.
        """
        self._lines = text.split("\n")
        # The cursor opens at the end of the buffer, so typing appends and the
        # last directive of a config file is the first thing you see.
        self._row = len(self._lines) - 1
        self._col = len(self._lines[self._row])
        self._original = text
        self._read_key: Callable[[], str] = (
            read_key if read_key is not None else platform_read_key
        )
        self._write = write if write is not None else print
        self.title = title

    def run(self) -> tuple[bool, str]:
        """Edit until the user saves or exits.

        Returns:
            ``(saved, text)``. ``saved`` is ``True`` only when the user pressed
            Ctrl+S. On a discard the original text is returned, so the caller
            can always use the returned text.
        """
        while True:
            self._render()
            key = self._read_key()
            if key == KEY_CTRL_S:
                return True, self.text()
            if key in (KEY_CTRL_X, KEY_ESC):
                return False, self._original
            self._apply(key)

    def text(self) -> str:
        """The current buffer contents."""
        return "\n".join(self._lines)

    def _apply(self, key: str) -> None:
        """Apply one key to the buffer."""
        if key == KEY_LEFT:
            self._col = max(0, self._col - 1)
        elif key == KEY_RIGHT:
            self._col = min(len(self._lines[self._row]), self._col + 1)
        elif key == KEY_UP:
            self._move_row(-1)
        elif key == KEY_DOWN:
            self._move_row(1)
        elif key == KEY_HOME:
            self._col = 0
        elif key == KEY_END:
            self._col = len(self._lines[self._row])
        elif key == KEY_BACKSPACE:
            self._backspace()
        elif key == KEY_DELETE:
            self._delete()
        elif key == KEY_ENTER:
            self._split_line()
        elif key == KEY_TAB:
            self._insert("\t")
        elif len(key) == 1 and key.isprintable():
            self._insert(key)

    def _move_row(self, delta: int) -> None:
        """Move the cursor to the row above or below, keeping the column."""
        row = min(max(0, self._row + delta), len(self._lines) - 1)
        self._row = row
        self._col = min(self._col, len(self._lines[row]))

    def _insert(self, char: str) -> None:
        """Insert a character at the cursor."""
        line = self._lines[self._row]
        self._lines[self._row] = line[: self._col] + char + line[self._col :]
        self._col += 1

    def _backspace(self) -> None:
        """Delete the character before the cursor, joining lines when needed."""
        if self._col > 0:
            line = self._lines[self._row]
            self._lines[self._row] = line[: self._col - 1] + line[self._col :]
            self._col -= 1
        elif self._row > 0:
            previous = self._lines[self._row - 1]
            self._lines[self._row - 1] = previous + self._lines[self._row]
            del self._lines[self._row]
            self._row -= 1
            self._col = len(previous)

    def _delete(self) -> None:
        """Delete the character at the cursor."""
        line = self._lines[self._row]
        if self._col < len(line):
            self._lines[self._row] = line[: self._col] + line[self._col + 1 :]

    def _split_line(self) -> None:
        """Split the current line at the cursor."""
        line = self._lines[self._row]
        head = line[: self._col]
        tail = line[self._col :]
        self._lines[self._row] = head
        self._lines.insert(self._row + 1, tail)
        self._row += 1
        self._col = 0

    def _render(self) -> None:
        """Draw the buffer and place the cursor."""
        self._write(_CLEAR)
        if self.title:
            self._write(f"{self.title}\n")
        for line in self._lines:
            self._write(f"{line}\n")
        self._write("^S save  ^X exit\n")
        self._write(f"\x1b[{self._row + 1};{self._col + 1}H")
