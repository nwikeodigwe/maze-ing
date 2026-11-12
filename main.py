"""Entry point for A-maze-ing Delft, a terminal text-adventure.

Importing ``config`` first is required: it loads ``.env``, creates the SQLite schema and constructs the
process-wide :class:`src.state.State`. When executed as a script the current room is rendered once and the
main loop in :class:`src.engine.Engine` takes over until the player quits.
"""

import io
import sys
import config  # noqa: F401  (loads .env)

from typing import cast

from src.engine import Engine
from src.room import Room
from src.utils.display import clear
from logger import logger

cast(io.TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8", errors="replace")

if __name__ == "__main__":
    room = Room()
    engine = Engine()
    try:
        logger.info("Game started")
        room.render()
        engine.run()
    except (KeyboardInterrupt, EOFError):
        logger.info("Game ended")
        clear()
        engine.shutdown()
