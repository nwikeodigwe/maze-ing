"""Generate unique, human-readable usernames for new players."""

import random
import re
from pathlib import Path

from db import connection

PREFIXES = ["Operator", "Cyber", "Null", "Cipher", "Agent", "Ghost", "Vector", "Node"]
CALLSIGNS = ["Aegis", "Vex", "Echo", "Kilo", "Zero", "Nexus", "Drift", "Sol"]


def generate_random_username() -> str:
    """Generates a random username and verifies it does not exist in the database."""
    with connection() as conn:
        while True:
            # 1. Build a candidate username
            prefix = random.choice(PREFIXES)
            callsign = random.choice(CALLSIGNS)
            suffix = random.randint(100, 999)
            candidate = f"{prefix}_{callsign}_{suffix}"

            # 2. Check SQLite DB for existence
            cur = conn.execute("SELECT 1 FROM users WHERE name = ?", (candidate,))
            if cur.fetchone() is None:
                return candidate

def next_save_slot(name: str) -> str:
    """Return the next unused auto-save slot for ``name``.

    Slots are named ``<name>_save_slot_<n>``; ``n`` is one more than the highest number found in ``data/saves``, so
    gaps from deleted files are not reused.

    Args:
        name: Player name used as the slot prefix.

    Returns:
        The next slot name (without the ``.json`` extension).
    """
    base_dir = Path(__file__).resolve().parent
    save_dir = base_dir / "data" / "saves"

    prefix = f"{name}_save_slot_"
    numbers = []
    if save_dir.exists():
        for path in save_dir.glob(f"{prefix}*.json"):
            match = re.fullmatch(rf"{re.escape(prefix)}(\d+)\.json", path.name)
            if match:
                numbers.append(int(match.group(1)))
    return f"{prefix}{max(numbers, default=0) + 1}"
