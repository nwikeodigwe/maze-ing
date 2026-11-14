import sqlite3
from contextlib import contextmanager

from pathlib import Path
from collections.abc import Iterator


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path if path is not None else Path(__file__).parent / "data" / "game.db"
        self.__setup()


    def __setup(self) -> None:
        """Create the tables idempotently."""
        schema = """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );

            CREATE TABLE IF NOT EXISTS saves (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                slot       TEXT NOT NULL UNIQUE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );

            CREATE TABLE IF NOT EXISTS scoreboard (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                score            INTEGER NOT NULL,
                avg_room_time    TEXT NOT NULL,
                exploration_time TEXT NOT NULL,
                assembly_time    TEXT NOT NULL,
                created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            """
        with self.connection() as conn:
            conn.executescript(schema)

    def connect(self, db_path: Path | None = None) -> sqlite3.Connection:
        """Open a connection with FK enforcement and ``sqlite3.Row`` access.

        Args:
            db_path: Database file to open. Defaults to :data:`DATABASE_PATH`. Parent directories are created if
                missing.

        Returns:
            An open connection. The caller is responsible for closing it; prefer :func:`connection`.
        """

        path = db_path if db_path is not None else self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection that commits on success and always closes.


        Yields:
            An open connection. The transaction is committed when the block exits normally and rolled back if it raises.

        Raises:
            Exception: Any exception raised inside the ``with`` block is re-raised after the rollback.
        """
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
