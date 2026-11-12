import textwrap
from datetime import datetime, timezone
from typing import Any

from config import state
from src.models.scoreboard import Scoreboard
from src.models.user import User
from src.phase import Phase
from src.rooms.front_desk import FrontDesk
from src.rooms.lab import Lab
from src.rooms.lobby import Lobby
from src.rooms.teachers_room_1 import TeachersRoomOne
from src.rooms.teachers_room_2 import TeachersRoomTwo
from src.rooms.teachers_room_4 import TeachersRoomFour
from src.state import State
from src.utils.colors import Colors
from src.utils.time import format_timestamp
from src.utils.display import out, colorize

STATUS_FLAG_LABELS = {
    "fr1_user_registered": "Front desk registration",
    "tr1_desk_unlocked": "Teachers Room 1 desk unlocked",
    "tr2_whiteboard_inspected": "Teachers Room 2 whiteboard inspected",
    "tr4_drawer_decrypted": "Teachers Room 4 drawer decrypted",
    "tr4_secret_key_copied": "Teachers Room 4 secret key copied",
    "lab_power_on": "Lab power restored",
}

class Engine(Phase, FrontDesk, Lobby, Lab, TeachersRoomOne, TeachersRoomTwo, TeachersRoomFour):
    def __init__(self, game_state: State = state, color: Colors | None = None) -> None:
        super().__init__()
        self.scoreboard = Scoreboard()
        self.user = User()
        self.color = color or Colors()
        self.state = game_state
        # State methods render feedback through the active engine's room view.
        self.state.render_room = self.render

    def inventory(self) -> None:
        """Show carried items and how many assembly parts are held. Pauses the game clock."""
        width = int(self.terminal_width)
        self.session["duration"]["pause"] = True
        self.header(self.colorize(text="INVENTORY", color_code=self.color.BRIGHT_CYAN + self.color.BOLD))
        if not self.player["inventory"]:
            self.out()
            self.out(
                self.colorize(
                    text="Your inventory is currently empty.".center(width),
                    color_code=self.color.DIM
                )
            )
            self.out()
            return

        assembly_parts_count = 0
        for item in self.player["inventory"]:
            item_data = self.items[item]

            if item_data["is_assembly_part"]:
                assembly_parts_count += 1
                tag = f" {self.colorize('[ASSEMBLY PART]', self.color.BRIGHT_GREEN)}"
            else:
                tag = ""

            self.out(f" • {self.colorize(item_data['name'], self.color.BRIGHT_YELLOW)}{tag}")
            self.out(f"   {self.colorize(item_data['description'], self.color.DIM)}")

        self.out(
            self.colorize(
                f"\nAssembly Components in Inventory: {assembly_parts_count}/{len(self.workbench['required_parts'])}",
                self.color.BRIGHT_WHITE
            )
        )
        self.out()

    def helper(self) -> None:
        """Show the help menu. Pauses the game clock.

        Uses ``rich`` tables when available and plain text otherwise. The ``Assembly`` command group is hidden until the
        ``ASSEMBLY`` phase.
        """
        self.session["duration"]["pause"] = True
        groups = [
            group for group in self.help_commands
            if
            group["title"] != "Assembly" or self.session["phase"] == "ASSEMBLY"
        ]

        try:
            import os

            from rich.console import Console
            from rich.table import Table


        except ModuleNotFoundError:
            self.out("Available Commands:")
            for group in groups:
                self.out(f"[{group['title']}]")
                for cmd in group["commands"]:
                    self.out(
                        f"  {cmd['command']:<24} {cmd['description']}  e.g. {cmd['example']}"
                    )
            return None

        else:
            self.header(self.colorize(text="HELP MENU", color_code=self.color.INFO + self.color.BOLD))
            console = Console(
                highlight=False, force_terminal=None if os.getenv("NO_COLOR") else True
            )
            for group in groups:
                table = Table(
                    title=group["title"], show_header=True, header_style="bold"
                )
                table.add_column("Command", style="cyan", no_wrap=True)
                table.add_column("Description")
                table.add_column("Example", style="dim")
                for cmd in group["commands"]:
                    table.add_row(cmd["command"], cmd["description"], cmd["example"])
                console.print(table)

    def inspect(self, details) -> None:
        """Inspect an interactable in the current room.

        Only a few targets are valid, each in one specific room (lobby ``terminal``, ``teachers_room_1`` ``desk``,
        ``lab_d2_001`` ``workbench``, ``teachers_room_2`` ``whiteboard``, ``front_desk`` ``receptionist``,
        ``teachers_room_4`` ``computer``). Anything else renders a "not in this room" error. Inspecting the whiteboard
        sets the ``tr2_whiteboard_inspected`` flag.

        Args:
            details: Parsed details with ``"target"``.
        """
        target = details["target"]
        current_room = self.player["current_room"]
        if target == "terminal" and current_room == "lobby":
            self.inspect_terminal()
            return None
        elif target == "desk" and current_room == "teachers_room_1":
            self.inspect_desk()
            return None
        elif target == "workbench" and current_room == "lab_d2_001":
            self.render_workbench()
            return None
        elif target == "whiteboard" and current_room == "teachers_room_2":
            self.inspect_whiteboard()
            return None
        elif target == "receptionist" and current_room == "front_desk":
            self.inspect_receptionist()
            return None
        elif target == "computer" and current_room == "teachers_room_4":
            self.inspect_computer()
            return None
        elif target == "note" and current_room == "teachers_room_4":
            self.inspect_note()
            return None
        else:
            self.render(
                text=self.colorize(
                    "The item you're trying to inspect is unavailable", color_code=self.color.RED
                )
            )
            return None

    def use(self, details: Any) -> None:
        """Use an item, with behaviour depending on the room.

        In ``teachers_room_1`` the item is treated as a desk code, in ``lab_d2_001`` it is installed on the
        workbench, and elsewhere nothing can be used (the player is told whether the item is missing or simply useless
        there).

        Args:
            details: Parsed details with ``"target"`` (item) and ``"indirect"`` (optional target).
        """
        item = details["target"]
        target = details["indirect"]
        if self.player["current_room"] == "teachers_room_1":
            self.use_desk_code(item, target)
            return None
        if self.player["current_room"] == "lab_d2_001":
            self.use_on_workbench(item)
            return None
        else:
            pi = self.player["inventory"]
            if item not in pi:
                self.render(
                    text=self.colorize(
                        f"You are currently do not have '{item}' in your inventory.",
                        color_code=self.color.RED
                    )
                )
                return None
            self.render(
                text=self.colorize(
                    f"You cannot use that {item} on {target}.", color_code=self.color.RED
                )
            )
            return None

    def take(self, details: Any) -> None:
        """Move an item from the current room into the inventory.

        Args:
            details: Parsed details with ``"target"`` (item id). Renders an error if the item is not in the room.
        """
        item = details["target"]
        current_room = self.player["current_room"]
        room_data = self.rooms[current_room]
        if item not in room_data["items"]:
            self.render(text=self.colorize(f"There is no '{item}' here.", color_code=self.color.RED))
            return None
        room_data["items"].remove(item)
        self.player["inventory"].append(item)
        itm = self.items[item]
        self.render(self.colorize(f"You picked up {itm['name']}", self.color.BRIGHT_GREEN))
        return None

    def drop(self, details: Any) -> None:
        """Move an item from the inventory into the current room.

        Args:
            details: Parsed details with ``"target"`` (item id). Renders an error if the item is unknown or not carried.
        """
        item = details["target"]
        item_data = self.items.get(item)
        if item_data is None:
            self.render(text=self.colorize(f"There is no item called '{item}'.", color_code=self.color.RED))
            return None
        current_room = self.player["current_room"]
        room_data = self.rooms[current_room]
        if item not in self.player["inventory"]:
            self.render(
                text=self.colorize(
                    f"You currently do not have '{item_data['name']}' here.",
                    color_code=self.color.RED
                )
            )
            return None
        self.player["inventory"].remove(item)
        self.rooms[current_room]["items"].append(item)
        self.render(
            self.colorize(
                f"You dropped {item_data['name']} in {room_data['name']}", self.color.BRIGHT_GREEN
            )
        )
        return None

    def shutdown(self) -> None:
        """Stop the main loop, print the final status screen and a farewell message."""
        self.status()
        self.persist()
        self.running = False
        self.out(
            self.colorize(
                text="Goodbye. see you again soon".center(self.terminal_width),
                color_code=self.color.BRIGHT_GREEN
            )
        )
        return None

    def register(self, details: Any) -> None:
        """Create a user profile and attach it to the player. Only works in ``front_desk``.

        Args:
            details: Parsed details with ``"target"`` (desired name). A taken name or database error is rendered,
                not raised.
        """
        name = details["target"]
        if not self.player["current_room"] == "front_desk":
            self.render(
                self.colorize(text="You can only register at the front desk", color_code=self.color.RED)
                )
            return None
        user = self.user.find().where(name=name).first()
        if not user:
            try:
                user_id = self.user.create(name)
                self.player["name"] = name
                self.player["id"] = user_id
                self.render(
                    text=self.colorize(
                        f"You have successfully registered a profile as {name}",
                        color_code=self.color.BRIGHT_GREEN
                    )
                )
                return None
            except Exception as e:
                self.render(text=self.colorize(str(e), color_code=self.color.RED))
                return None
        self.render(
            text=self.colorize(
                f"The name '{name}' is already taken. Please try another one.",
                color_code=self.color.RED
            )
        )
        return None

    def login(self, details: Any) -> None:
        """Attach an existing user profile to the player. Only works in ``front_desk``.

        Args:
            details: Parsed details with ``"target"`` (user name).
        """
        name = details["target"]
        if not self.player["current_room"] == "front_desk":
            self.render(
                self.colorize(text="You can only register at the front desk", color_code=self.color.RED)
                )
            return None
        if name is None:
            self.render(text=self.colorize("Please enter a name", color_code=self.color.RED))
            return None
        user = self.user.find().where(name=name).first()
        if not user:
            self.render(self.colorize(f"User '{name}' does not exist", color_code=self.color.ERROR))
            return None
        self.player["name"] = name
        self.player["id"] = user["id"]
        self.render(self.colorize(f"You are currently logged in as {name}", color_code=self.color.SUCCESS))
        return None

    def logout(self) -> None:
        """Detach the user profile from the player (back to ``guest``). Only works in ``front_desk`` while logged in.

        Game progress is kept; only the identity changes.
        """
        if self.player["current_room"] != "front_desk":
            self.render(
                self.colorize(
                    text="You can only complete this operation at the front desk",
                    color_code=self.color.ERROR
                )
            )
            return None
        if not self.player["id"]:
            self.render(self.colorize(text="You are currently not logged in!", color_code=self.color.ERROR))
            return None
        old_name = self.player["name"]
        self.player["id"] = None
        self.player["name"] = "guest"
        self.render(
            self.colorize(
                text=f"You have been logged out from {old_name}",
                color_code=self.color.SUCCESS
            )
        )
        return None

    def restart(self) -> None:
        """Reset the game to the default template, keeping the player's name and id.

        The clock is restarted at ``00:00:00`` and unpaused.
        """
        # Keep a copy only to carry the player's identity across the reset below.
        player = {**self.player}
        self.state.reset()
        self.player["name"] = player["name"]
        self.player["id"] = player["id"]
        now = datetime.now(timezone.utc).isoformat()
        self.session["timestamp"] = now
        self.session["duration"]["last_write"] = now
        self.session["duration"]["value"] = "00:00:00"
        self.session["duration"]["pause"] = False
        self.render(text=self.colorize("New game!", color_code=self.color.BRIGHT_GREEN))

    def render_scoreboard(self) -> None:
        """Show the ranked scoreboard (best score first, then fastest total time)."""
        width = int(self.terminal_width)
        entries = self.scoreboard.find().all()
        self.header(self.colorize(text="GAME SCOREBOARD", color_code=self.color.INFO + self.color.BOLD))
        if not entries:
            self.out()
            self.out(self.colorize(text="No entries found!".center(width), color_code=self.color.DIM))
            return None

        rows = []
        for rank, entry in enumerate(entries, start=1):
            user = self.user.find().where(id=entry["user_id"]).first()
            player_name = user["name"] if user else f"Unknown ({entry['user_id']})"
            rows.append((rank, player_name, entry))

        self.out(
            f"{'Rank':<6}{'Player':<20}{'Score':>8}  "
            f"{'Avg Room':<10}{'Exploration':<12}{'Assembly':<10}"
        )
        for rank, player_name, entry in rows:
            self.out(
                f"{rank:<6}{player_name:<20}{entry['score']:>8}  "
                f"{entry['avg_room_time']:<10}{entry['exploration_time']:<12}"
                f"{entry['assembly_time']:<10}"
            )

        return None

    def __wrap_status_text(self, text: str, width: int) -> list[str]:
        """Wrap status text, preferring comma-separated item boundaries.

        Args:
            text: Text to wrap.
            width: Maximum line width.

        Returns:
            At least one line; items are kept whole where they fit, otherwise long words are broken.
        """
        if ", " in text:
            lines = []
            current = ""
            for item in text.split(", "):
                candidate = f"{current}, {item}" if current else item
                if len(candidate) <= width:
                    current = candidate
                else:
                    if current:
                        lines.append(f"{current},")
                    current = item
            if current:
                lines.append(current)

            wrapped = []
            for line in lines:
                if len(line) <= width:
                    wrapped.append(line)
                else:
                    wrapped.extend(
                        textwrap.wrap(line, width=width, break_long_words=True) or [""]
                    )
            return wrapped or [""]

        return textwrap.wrap(text, width=width, break_long_words=True) or [""]

    def __print_status_row(self, label: str, value: str) -> None:
        """Print one status row, wrapping long values at ``width``.

        Short values are right-aligned; wrapped values continue on indented lines. Multi-line values are wrapped
        per line.

        Args:
            label: Row label.
            value: Row value, possibly containing newlines.
            width: Total terminal width.
        """

        width = self.terminal_width
        prefix = f" {label}:"
        indent = " " * (len(prefix) + 1)
        available = max(1, width - len(prefix) - 2)
        first, *rest = value.splitlines() or [""]

        chunks = self.__wrap_status_text(first, available)
        if len(chunks) == 1:
            gap = max(1, width - len(prefix) - len(chunks[0]) - 1)
            self.out(f"{prefix}{' ' * gap}{chunks[0]}")
        else:
            self.out(f"{prefix} {chunks[0]}")
            for chunk in chunks[1:]:
                self.out(f"{indent}{chunk}")

        for line in rest:
            for chunk in self.__wrap_status_text(line, available):
                self.out(f"{indent}{chunk}")

    def saves(self):
        """Print the logged-in player's saves with creation dates."""
        width = self.terminal_width
        self.header(self.colorize("SAVED CHECKPOINTS", self.color.CYAN))
        ok, msg = self.list_saves()
        if not ok:
            out(self.colorize(text=msg, color_code=self.color.BRIGHT_YELLOW + self.color.BOLD))
            return None
        for row in msg:
            date = format_timestamp(row["created_at"])
            space_needed = width - len(date) - len(row["slot"])
            out(row["slot"], end=f"{' ' * space_needed}")
            out(colorize(f"{date}", self.color.DIM))
        return None

    def status(self) -> None:
        """Show the status screen: player, room, phase, time, exploration progress, challenges and inventory.

        Pauses the game clock.
        """
        self.session["duration"]["pause"] = True
        self.header(self.colorize(text="STATUS MENU", color_code=self.color.BRIGHT_YELLOW + self.color.BOLD))

        current_room = self.player["current_room"]
        room_name = self.rooms[current_room]["name"]
        timestamp = self.session["timestamp"]
        start_time = format_timestamp(timestamp) if timestamp else "Unknown"
        duration = self.session["duration"]["value"] or "00:00:00"

        # Order-preserving de-duplication of visited rooms (history plus current room).
        visited_ids = list(dict.fromkeys([*self.player["move"], current_room]))
        visited_names = [
            self.rooms[room_id]["name"] for room_id in visited_ids
        ]
        recent_visited = visited_names[-5:]
        visited_text = ", ".join(recent_visited) or "None"
        if len(visited_names) > 5:
            visited_text = f"... {visited_text}"
        total_rooms = len(self.rooms)
        explored_percent = round(len(visited_ids) / total_rooms * 100)

        completed = [
            STATUS_FLAG_LABELS.get(flag, flag.replace("_", " ").title())
            for flag, enabled in self.flags.items()
            if enabled
        ]
        installed = len(self.workbench["installed_parts"])

        inv = self.player["inventory"]
        inventory_names = [
            self.items[item_id]["name"] for item_id in inv
        ]
        assembly_parts = sum(
            1 for item_id in inv if self.items[item_id]["is_assembly_part"]
        )

        required = len(self.workbench["required_parts"])
        ready_text = "ready" if self.workbench["is_ready"] else "not ready"

        inventory_items = ", ".join(inventory_names) or "Empty"

        challenge_text = f"{len(completed)}/{len(self.flags)}"
        if completed:
            challenge_text += " " + ", ".join(completed)

        rows = [
            ("Name", self.player["name"].title()),
            ("Room", room_name),
            ("Phase", self.session["phase"]),
            None,
            ("Started", start_time),
            ("Time spent", duration),
            None,
            ("Explored", f"{len(visited_ids)}/{total_rooms} ({explored_percent}%)"),
            ("Visited", visited_text),
            ("Challenges", challenge_text),
            ("Assembly", f"{installed}/{required} installed ({ready_text})"),
            None,
            ("Inventory", inventory_items),
            ("Assembly parts", str(assembly_parts)),
        ]

        for row in rows:
            if row is None:
                self.out()
                continue
            label, value = row
            self.__print_status_row(label, value)

        self.out()
        return None

    def commands(self, verb, details) -> None:
        """Dispatch a parsed command to its handler.

        ``clear`` and ``activate`` are handled elsewhere (screen clearing and :mod:`src.phase`), and verbs without a
        handler (including ``UNKNOWN``, ``INVALID`` and ``EMPTY``) are silently ignored here; callers report those.

        Args:
            verb: Canonical verb returned by :func:`src.parser.parse`.
            details: Details dict returned by :func:`src.parser.parse`.
        """
        if verb == "quit":
            self.shutdown()
            return
        if verb == "restart":
            self.restart()
            return
        elif verb == "help":
            self.helper()
            return
        elif verb == "scoreboard":
            self.render_scoreboard()
            return
        elif verb == "status":
            self.status()
            return
        elif verb == "inventory":
            self.inventory()
            return
        elif verb == "use":
            self.use(details)
            return
        elif verb == "register":
            self.register(details)
            return
        elif verb == "login":
            self.login(details)
            return
        elif verb == "logout":
            self.logout()
            return
        elif verb == "save":
            self.save(details)
            return
        elif verb == "saves":
            self.saves()
            return
        elif verb == "load":
            self.load(details)
            return
        elif verb == "inspect":
            self.inspect(details)
            return
        elif verb == "look":
            self.render()
            return
        elif verb == "take":
            self.take(details)
            return
        elif verb == "drop":
            self.drop(details)
            return
        elif verb == "go":
            self.move(details)
            return

    def run(self) -> None:
        # Imported lazily to break the engine_functional <-> phase circular import.
        """Run the main game loop until ``state["running"]`` becomes false."""
        self.player["current_room"] = self.spawn()
        while self.running:
            self.auto()
            match self.session["phase"]:
                case self.mode.EXPLORATION:
                    self.exploration()
                case self.mode.ASSEMBLY:
                    self.assembly()
                case self.mode.CHAT:
                    self.chat()
                case _:
                    self.exploration()
