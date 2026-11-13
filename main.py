"""Entry point for A-maze-ing Delft, a terminal text-adventure.

Importing ``config`` first is required: it loads ``.env``, creates the SQLite schema and constructs the
process-wide :class:`src.state.State`. When executed as a script the current room is rendered once and the
main loop in :class:`src.engine.Engine` takes over until the player quits.
"""

import io
import sys
import config  # noqa: F401  (loads .env)
import schedule
import threading
import time

from typing import cast

from src.engine import Engine
from src.room import Room
from logger import logger

cast(io.TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8", errors="replace")
room = Room()
engine = Engine()

def cron(main: Engine) -> None:
    schedule.every(1).second.do(main.auto)
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=cron, args=(engine,), daemon=True).start()

if __name__ == "__main__":
    logger.info("Game started")
    try:
        room.render()
        engine.run()
    except (KeyboardInterrupt, EOFError):
        engine.shutdown()
