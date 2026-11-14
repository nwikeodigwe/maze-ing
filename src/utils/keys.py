"""Cross-platform single-key reading, normalized to stable tokens.

Terminals report special keys differently: POSIX terminals send escape
sequences (``\\x1b[A`` for up) while Windows consoles send a prefix byte
followed by a code (``\\xe0H``). This module turns both into the same
tokens so callers never have to know which platform they are on.
"""

from __future__ import annotations

import sys

from collections.abc import Callable

KEY_UP = "UP"
KEY_DOWN = "DOWN"
KEY_LEFT = "LEFT"
KEY_RIGHT = "RIGHT"
KEY_HOME = "HOME"
KEY_END = "END"
KEY_BACKSPACE = "BACKSPACE"
KEY_DELETE = "DELETE"
KEY_ENTER = "ENTER"
KEY_TAB = "TAB"
KEY_ESC = "ESC"
KEY_CTRL_S = "CTRL_S"
KEY_CTRL_X = "CTRL_X"

_POSIX_CSI = {
    "A": KEY_UP,
    "B": KEY_DOWN,
    "C": KEY_RIGHT,
    "D": KEY_LEFT,
    "H": KEY_HOME,
    "F": KEY_END,
}

_POSIX_TILDE = {
    "1": KEY_HOME,
    "3": KEY_DELETE,
    "4": KEY_END,
}

_POSIX_SS3 = {
    "H": KEY_HOME,
    "F": KEY_END,
}

_WINDOWS = {
    "H": KEY_UP,
    "P": KEY_DOWN,
    "K": KEY_LEFT,
    "M": KEY_RIGHT,
    "G": KEY_HOME,
    "O": KEY_END,
    "S": KEY_DELETE,
}

_CONTROL = {
    "\r": KEY_ENTER,
    "\n": KEY_ENTER,
    "\x08": KEY_BACKSPACE,
    "\x7f": KEY_BACKSPACE,
    "\t": KEY_TAB,
    "\x1b": KEY_ESC,
    "\x13": KEY_CTRL_S,
    "\x18": KEY_CTRL_X,
}


def _platform_reader() -> Callable[[], str]:
    """Return a raw-character reader for the current platform."""
    if sys.platform == "win32":
        import msvcrt

        return msvcrt.getwch

    import termios
    import tty

    def read() -> str:
        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)

    return read


def read_key(read: Callable[[], str] | None = None) -> str:
    """Read one keypress and return a stable token or the literal character.

    Args:
        read: Optional raw-character reader, mainly for tests. Defaults to the
            platform's own single-key reader.

    Returns:
        One of the ``KEY_*`` tokens, or the single character that was typed.
    """
    reader = read if read is not None else _platform_reader()
    char = reader()

    if char == "\x1b":
        return _read_posix(reader)

    if char in ("\xe0", "\x00"):
        code = reader()
        return _WINDOWS.get(code, code)

    return _CONTROL.get(char, char)


def _read_posix(reader: Callable[[], str]) -> str:
    """Resolve a POSIX escape sequence to a token."""
    second = reader()
    if second == "[":
        third = reader()
        if third.isdigit():
            # A parameterised sequence such as ESC [ 3 ~ (delete).
            if reader() == "~":
                return _POSIX_TILDE.get(third, KEY_ESC)
            return KEY_ESC
        return _POSIX_CSI.get(third, KEY_ESC)
    if second == "O":
        return _POSIX_SS3.get(reader(), KEY_ESC)
    return KEY_ESC
