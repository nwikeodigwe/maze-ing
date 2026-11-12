"""Terminal output helpers for the object-oriented game engine.

All output funnels through :func:`out` so text is downgraded to what the
Windows ``cp1252`` console can display. ``state`` is imported lazily inside
each function that needs it to avoid a circular import with :mod:`config`,
which constructs the :class:`~src.state.State` while loading.
"""

from subprocess import run


def clear() -> None:
    """Clear the terminal screen (Windows/posix/PyCharm-safe)."""
    try:
        from rich.console import Console

        Console().clear()
    except ModuleNotFoundError:
        import os

        if os.getenv("PYCHARM_HOSTED"):
            import builtins

            builtins.print("\n" * 50)
        else:
            run(["cls" if os.name == "nt" else "clear"], shell=True)


def prompt(message: str | None = None) -> str:
    """Read one line of player input.

    Args:
        message: Optional label shown before the ``>`` marker. Defaults to a bare ``>`` prompt.

    Returns:
        The input with surrounding whitespace stripped.

    Raises:
        EOFError: If standard input is closed.
    """
    if message is None:
        return input("\n> ").strip()
    return input(f"\n{message} >").strip()


def safe(text: str) -> str:
    """Make ``text`` printable on a ``cp1252`` console.

    Box-drawing and arrow characters are first transliterated to ASCII; any remaining unencodable character is
    replaced with ``?`` rather than raising.

    Args:
        text: Text that may contain non-cp1252 characters.

    Returns:
        Text that can always be encoded as ``cp1252``.
    """
    # Transliterate the glyphs the game uses that cp1252 cannot encode.
    table = str.maketrans({"─": "-", "═": "=", "•": "*", "→": "->", "←": "<-"})
    text = text.translate(table)
    try:
        text.encode("cp1252")
        return text
    except UnicodeEncodeError:
        return text.encode("cp1252", errors="replace").decode("cp1252")


def colorize(text: str, color_code: str) -> str:
    """Wrap ``text`` in an ANSI colour code and reset sequence.

    Args:
        text: Text to colour.
        color_code: ANSI escape sequence (see :mod:`src.utils.colors`).

    Returns:
        The coloured text, or ``text`` unchanged when colours are disabled.
    """
    from config import state

    return f"{color_code}{text}\033[0m" if state.enable_colors else text


def out(text: str = "", end: str | None = None) -> None:
    """Print ``text`` after making it safe for the console encoding.

    Args:
        text: Text to print.
        end: Line terminator passed to ``print``; ``None`` means the default newline.
    """
    import builtins

    builtins.print(safe(text), end=end)


def draw_line(char: str = "-") -> None:
    """Print a dimmed horizontal rule spanning the configured terminal width.

    Args:
        char: Character repeated to build the line.
    """
    from config import state

    out(colorize(char * state.terminal_width, "\033[2m"))
