from typing import Any

from database import Database


class Save(Database):
    def __init__(self, data: dict | None = None) -> None:
        super().__init__()
        self.user = data if data else {}

    def create(self,  slot: str,  user_id: int | None = None,) -> int | None:
        """Record that ``user_id`` owns the save file ``slot``.

        Args:
            slot: Unique save slot name (the file stem under ``data/saves``).
            user_id: Owning user's id.

        Returns:
            The new row id.

        Raises:
            sqlite3.IntegrityError: If the slot already exists or ``user_id`` is unknown.
        """
        if user_id:
            self.user["id"] = user_id
        with self.connection() as conn:
            cur = conn.execute(
                "INSERT INTO saves (slot, user_id) VALUES (?, ?)", (slot, self.user["id"])
            )
            return cur.lastrowid

    def find(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """List a user's saves.


        Returns:
            Save rows as dicts (possibly empty), in insertion order.
        """
        if user_id:
            self.user["id"] = user_id
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM saves WHERE user_id = ?", (self.user["id"],)
            ).fetchall()
        return [dict(row) for row in rows]

    def find_unique(self, slot: str, user_id: int | None = None, ) -> dict[str, Any] | None:
        """Find one save owned by a user.

        Args:
            user_id: Owning user's id.
            slot: Save slot name.

        Returns:
            The save row as a ``dict``, or ``None`` if the user does not own that slot.
        """
        if user_id:
            self.user["id"] = user_id
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM saves WHERE user_id = ? AND slot = ?",
                (self.user["id"], slot),
            ).fetchone()
        return dict(row) if row else None