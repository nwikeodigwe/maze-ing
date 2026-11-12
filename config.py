"""Process-wide configuration and start-up side effects.

Importing this module has side effects by design: it loads environment variables from ``.env`` (API keys for the
chat providers), creates the SQLite schema via :class:`database.Database`, and constructs the live game state via
:class:`src.state.State`.

Attributes:
    PROJECT_ROOT: Absolute path of the repository root (the directory containing this file).
    database: The process-wide database helper, created on import.
    state: The process-wide game state, created on import.
"""
import logging

from pathlib import Path
from dotenv import load_dotenv

from database import Database
from src.state import State

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# Configure logging to write to a file
logging.basicConfig(
    filename="data/game.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a",  # 'a' to append (default), 'w' to overwrite each run
)

database = Database()
state = State()
