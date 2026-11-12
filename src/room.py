import builtins
import re

from config import state
from src.utils.display import clear, prompt, safe
from src.utils.colors import Colors


class Room:
    """Shared room rendering and access to the active game state.

    Attributes not defined on the room itself are looked up on ``self.state``,
    so ``self.player``, ``self.session``, ``self.items`` and state methods such
    as ``self.auto()`` are available from every room and from ``Engine``.
    """

    def __init__(self, game_state=None, make_safe=safe, colors = Colors) -> None:
        self.state = game_state if game_state is not None else state
        self.make_safe = make_safe
        self.color = colors()
        super().__init__()

    def __getattr__(self, name: str):
        state_obj = object.__getattribute__(self, "__dict__").get("state")
        if state_obj is not None:
            return getattr(state_obj, name)
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    # -- output helpers ---------------------------------------------------
    def clear(self) -> None:
        clear()

    def prompt(self, message: str | None = None) -> str:
        return prompt(message)

    def draw_line(self, char: str = "-") -> None:
        """Print a dimmed horizontal rule spanning the terminal width."""
        self.out(self.colorize(char * self.state.terminal_width, "\033[2m"))

    def colorize(self, text: str, color_code: str) -> str:
        """Wrap ``text`` in an ANSI colour code and reset sequence."""
        return f"{color_code}{text}\033[0m" if self.state.enable_colors else text

    def out(self, text: str = "", end: str | None = None) -> None:
        """Print ``text`` after making it safe for the console encoding."""
        builtins.print(self.make_safe(text), end=end)

    def header(self, content: str | None = None) -> None:
        """Print the top banner: phase, location/custom title, name, time and pause marker."""
        current_room = self.state.player["current_room"]
        room_data = self.state.rooms[current_room]

        self.draw_line("═")
        self.out(self.colorize(f"[{self.state.session['phase']}]", self.color.BRIGHT_MAGENTA))

        if content:
            visible_len = len(re.sub(r"\x1b\[[0-9;]*m", "", content))
            space_needed = max(
                1,
                self.state.terminal_width
                - visible_len
                - len(self.state.player["name"]),
            )
            self.out(content, end=f"{' ' * space_needed}")
            self.out(self.colorize(f"{self.state.player['name'].upper()}", self.color.DIM))
        else:
            space_needed = max(
                1,
                self.state.terminal_width
                - len(f"LOCATION: {room_data['name']}")
                - len(self.state.player["name"]),
            )
            self.out(
                self.colorize(
                    f"LOCATION: {room_data['name']}", self.color.BRIGHT_YELLOW + self.color.BOLD
                ),
                end=f"{' ' * space_needed}",
            )
            self.out(self.colorize(f"{self.state.player['name'].upper()}", self.color.DIM))

        duration = self.state.session["duration"]
        self.out(
            self.colorize(text=f"{duration['value']}", color_code=self.color.DIM + self.color.BOLD),
            end=" ",
        )
        self.out(
            self.colorize(
                text=f"{'[PAUSED]' if duration['pause'] else ''}",
                color_code=self.color.DIM,
            )
        )
        self.draw_line("═")

    def footer(self) -> None:
        """Print the exits, loose items and interactables of the current room."""
        current_room = self.state.player["current_room"]
        room_data = self.state.rooms[current_room]

        exits = room_data.get("exits") or {}
        if exits:
            formatted_exits = []
            for direction, target in exits.items():
                target_name = self.state.rooms.get(target, {}).get("name", target)
                formatted_exits.append(f"{direction.upper()} -> {target_name}")
            self.out(self.colorize(f"Exits: {', '.join(formatted_exits)}", self.color.CYAN))
        else:
            self.out(self.colorize("Exits: None available.", self.color.ERROR))

        room_items = room_data.get("items") or []
        if room_items:
            self.out(
                self.colorize(text="\nItems in area:", color_code=self.color.BRIGHT_WHITE + self.color.BOLD)
            )
            for item_id in room_items:
                item_data = self.state.items[item_id]
                display_name = item_data.get("name", item_id)
                component_tag = (
                    f" {self.colorize('[ASSEMBLY PART]', self.color.BRIGHT_GREEN)}"
                    if item_data.get("is_assembly_part")
                    else ""
                )
                self.out(
                    f"  • {self.colorize(display_name, self.color.BRIGHT_YELLOW)}{component_tag}"
                )

        interactables = (
            room_data.get("interactables")
            or room_data.get("interactable")
            or {}
        )
        if interactables:
            self.out(self.colorize("\nInteractables:", self.color.DIM + self.color.BOLD))
            for interactable in interactables.keys():
                self.out(f"  • {self.colorize(interactable, self.color.WHITE)}")

        self.out()

    def render(self, text: str | None = None, asset: str | None = None) -> None:
        """Redraw the current room: header, narrative, optional ASCII asset and footer."""
        self.state.session["duration"]["pause"] = False
        self.header()
        current_room = self.state.player["current_room"]
        room_data = self.state.rooms[current_room]

        if text is None:
            text = room_data["description"]

        if asset:
            print(asset)

        self.out(f"\n{text}\n")
        self.footer()