from enum import Enum

from src.langchain import Langchain
from src.parser import Parser
from src.room import Room
from src.utils.colors import Colors


class Mode(str, Enum):
    EXPLORATION = "EXPLORATION"
    ASSEMBLY = "ASSEMBLY"
    CHAT = "CHAT"


class Phase(Room):
    def __init__(self, phase: Mode = Mode.EXPLORATION, color: Colors | None = None) -> None:
        super().__init__()
        self.last_room_id: str | None = None
        self.phase: Mode = phase
        self.parser = Parser()
        self.langchain = Langchain(provider="gemini")
        self.color: Colors = color or Colors()

    def exploration(self) -> None:
        """Run one exploration prompt cycle."""
        raw = self.prompt()
        verb, details = self.parser.parse(raw)
        self.clear()
        self.commands(verb, details)
        if verb in ("UNKNOWN", "INVALID", "EMPTY"):
            self.render(
                self.colorize(
                    text="Invalid input. Please try again. type 'help' for a list of available commands.",
                    color_code=self.color.ERROR,
                )
            )
        return

    def assembly(self) -> None:
        """Run one assembly-phase cycle."""
        if not self.session["phases"]["assembly"]["activated"]:
            self.clear()
            self.render_workbench(
                self.colorize(
                    "Build your dream robot. type 'activate' to begin activation",
                    self.color.SUCCESS,
                )
            )
            self.session["phases"]["assembly"]["activated"] = True
            return
        raw = self.prompt()
        verb, details = self.parser.parse(raw)
        self.clear()
        self.commands(verb, details)
        if verb == "activate":
            self.activate()
        if verb in ("UNKNOWN", "INVALID", "EMPTY"):
            self.render(
                self.colorize(
                    "Invalid input. Please try again. type 'help' for a list of available commands.",
                    self.color.ERROR,
                )
            )
        return

    def chat(self) -> None:
        """Run one chat-phase cycle."""
        if not self.session["phases"]["chat"]["activated"]:
            self.clear()
            self.render(
                self.colorize(
                    f"Welcome to A-maze-ing-Delft chat mode! You can now freely talk to "
                    f"{self.session['phases']['chat']['robot']['name']}",
                    self.color.SUCCESS,
                )
            )
            self.session["phases"]["chat"]["activated"] = True
            return
        raw = self.prompt()
        verb, details = self.parser.parse(raw)
        self.clear()
        self.commands(verb, details)
        if (
            verb in ("UNKNOWN", "INVALID", "EMPTY")
            and self.player["current_room"] == "lab_d2_001"
        ):
            self.header()
            self.out()
            self.langchain.respond(raw)
            self.out()
            return
        if verb in ("UNKNOWN", "INVALID", "EMPTY"):
            self.render(
                self.colorize(
                    "Invalid input. Please try again. type 'help' for a list of available commands.",
                    self.color.ERROR,
                )
            )

        return