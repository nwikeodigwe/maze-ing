from typing import Any

from database import Database

class SaveQuery:
    def __init__(self, model: Database) -> None:
        self.model = model
        self.conditions: dict[str, Any] = {}

    def where(self, **conditions: Any) -> "SaveQuery":
        self.conditions.update(conditions)
        return self

    def first(self) -> dict[str, Any] | None:
        sql = "SELECT * FROM saves"
        if self.conditions:
            sql += " WHERE " + " AND ".join(
                f"{column} = ?" for column in self.conditions
            )
        with self.model.connection() as conn:
            row = conn.execute(sql, tuple(self.conditions.values())).fetchone()
        return dict(row) if row else None

    def all(self) -> list[dict[str, Any]]:
        """Return every matching save row, oldest first."""
        sql = "SELECT * FROM saves"
        if self.conditions:
            sql += " WHERE " + " AND ".join(
                f"{column} = ?" for column in self.conditions
            )
        sql += " ORDER BY id"
        with self.model.connection() as conn:
            rows = conn.execute(sql, tuple(self.conditions.values())).fetchall()
        return [dict(row) for row in rows]

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

    def find(self) -> SaveQuery:
        """Start a query over saves.

        Returns:
            A query object supporting ``where``/``first``/``all``.
        """
        return SaveQuery(self)