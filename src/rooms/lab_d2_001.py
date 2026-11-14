import time

from src.room import Room
from src.utils.loader import loader


class LabD2001(Room):
    def __init__(self):
        super().__init__()


    def inspect_server(self) -> None:
        player_name = self.state.player['name'] or "guest"
        loader(
            loading_time=1.2,
            label="Booting up workstation...",
            mode="LOADER",
        )
        time.sleep(1)
        self.clear()
        self.prompt(f"{player_name}@thuas-workstation:~$")
        return None