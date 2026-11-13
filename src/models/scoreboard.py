from typing import Any

from database import Database
from src.utils.time import parse_time_str


class ScoreboardQuery:
    def __init__(self, model: Database) -> None:
        self.model = model
        self.conditions: dict[str, Any] = {}

    def __total_time_seconds(self, entry: dict[str, Any]) -> float:
        """Return exploration plus assembly time of a scoreboard row in seconds.

        Args:
            entry: Scoreboard row as a dict.
        """
        return (
                parse_time_str(entry["exploration_time"]).total_seconds()
                + parse_time_str(entry["assembly_time"]).total_seconds()
        )

    def where(self, **conditions: Any) -> "ScoreboardQuery":
        self.conditions.update(conditions)
        return self

    def first(self) -> dict[str, Any] | None:
        sql = "SELECT * FROM scoreboard"
        if self.conditions:
            sql += " WHERE " + " AND ".join(
                f"{column} = ?" for column in self.conditions
            )
        with self.model.connection() as conn:
            row = conn.execute(sql, tuple(self.conditions.values())).fetchone()
        return dict(row) if row else None

    def all(self) -> list[dict[str, Any]]:
        """Return every matching row, best score first then fastest total time."""
        sql = "SELECT * FROM scoreboard"
        if self.conditions:
            sql += " WHERE " + " AND ".join(
                f"{column} = ?" for column in self.conditions
            )
        with self.model.connection() as conn:
            rows = conn.execute(sql, tuple(self.conditions.values())).fetchall()
        entries = [dict(row) for row in rows]
        entries.sort(
            key=lambda entry: (
                -entry["score"],
                self.__total_time_seconds(entry),
                entry["id"],
            )
        )
        return entries

class Scoreboard(Database):
    def create(self, data: dict) -> int | None:
        """Insert a scoreboard row.

            Args:
                data: data of the player who finished the game.

            Returns:
                The new row id.
            """
        with self.connection() as conn:
            cur = conn.execute(
                "INSERT INTO scoreboard "
                "(user_id, score, avg_room_time, exploration_time, assembly_time) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    data["user_id"],
                    data["score"],
                    data["avg_room_time"],
                    data["exploration_time"],
                    data["assembly_time"],
                ),
            )
            return cur.lastrowid

    def find(self):
        """Return scoreboard rows: highest score first, then fastest total time."""
        return ScoreboardQuery(self)
