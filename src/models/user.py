from pathlib import Path
from typing import Any

from database import Database


class UserQuery:
    def __init__(self, model: Database) -> None:
        self.model = model
        self.conditions: dict[str, Any] = {}

    def where(self, **conditions: Any) -> "UserQuery":
        self.conditions.update(conditions)
        return self

    def first(self) -> dict[str, Any] | None:
        sql = "SELECT * FROM users"
        if self.conditions:
            sql += " WHERE " + " AND ".join(
                f"{column} = ?" for column in self.conditions
            )
        with self.model.connection() as conn:
            row = conn.execute(sql, tuple(self.conditions.values())).fetchone()
        return dict(row) if row else None


class User(Database):
    def __init__(self, path: Path | None = None) -> None:
        super().__init__(path)
        self.data: dict[str, Any] = {"name": None, "id": None}

    def create(self, name: str | None = None) -> int | None:
        """Insert a new user.

        Args:
            name: Unique user name.

        Returns:
            The new user's row id.

        Raises:
            sqlite3.IntegrityError: If ``name`` is already taken.
        """
        if name:
            self.data["name"] = name
        with self.connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (name) VALUES (?)", (self.data["name"],)
            )
            return cur.lastrowid

    def find(self) -> UserQuery:
        """Start a query over users.

        Returns:
            A query object supporting ``where``/``first``.
        """
        return UserQuery(self)