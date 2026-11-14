"""Lobby room.

No lobby-specific logic is needed beyond the terminal interaction; its data
lives in ``data/default.json``.
"""
from src.assets.logo import logo
from src.room import Room


class Lobby(Room):
    def inspect_terminal(self) -> None:
        self.render(
            text=self.rooms["lobby"]["interactables"]["terminal"],
            asset=logo,
        )
        return None