from __future__ import annotations

import json
import os
import re

from datetime import datetime, timezone
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.alias import Alias
from src.models.save import Save
from src.utils.display import colorize, out
from src.utils.time import calculate_duration, parse_time_str
from src.utils.colors import Colors


class State:
    """In-memory game state plus persistence helpers.

    ``data`` is the single mutable source of truth. Configurable/static data
    (rooms, items, help text) is loaded from separate JSON files and merged in
    so callers can use either object attributes (``state.player``) or mapping
    access (``state["player"]``).
    """

    _PERSIST_KEYS = (
        "player",
        "workbench",
        "flags",
        "session",
        "running",
        "enable_colors",
        "terminal_width",
    )

    def __init__(self, colors: Colors | None = None) -> None:
        self.data: dict[str, Any] = {}
        self.help_commands: list = []
        self.render_room: Callable[..., None] | None = None
        self._saves = Save()

        self._BASE_DIR = Path(__file__).resolve().parent
        self.PROJECT_ROOT = self._BASE_DIR.parent
        self.DATA_DIR = self.PROJECT_ROOT / "data"
        self.DEFAULT_GAME_STATE_PATH = self.DATA_DIR / "default.json"
        self.USER_STATE_PATH = self.DATA_DIR / "user.json"
        self.ROOMS_STATE_PATH = self.DATA_DIR / "rooms.json"
        self.ITEMS_STATE_PATH = self.DATA_DIR / "items.json"
        self.HELP_COMMANDS_PATH = self.DATA_DIR / "help.json"
        self.SAVE_DIR = self.DATA_DIR / "saves"

        self.color = colors or Colors()

        self.__setup()

    # -- mapping protocol -------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self.data

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def clear(self) -> None:
        self.data.clear()

    def update(self, other: dict) -> None:
        self.data.update(other)

    # -- properties -------------------------------------------------------
    @property
    def player(self) -> dict:
        return self.data["player"]

    @property
    def session(self) -> dict:
        return self.data["session"]

    @property
    def workbench(self) -> dict:
        return self.data["workbench"]

    @property
    def flags(self) -> dict:
        return self.data["flags"]

    @property
    def rooms(self) -> dict:
        return self.data["rooms"]

    @property
    def items(self) -> dict:
        return self.data["items"]

    @property
    def running(self) -> bool:
        return bool(self.data.get("running", True))

    @running.setter
    def running(self, value: bool) -> None:
        self.data["running"] = bool(value)

    @property
    def terminal_width(self) -> int:
        return int(self.data.get("terminal_width", 120))

    @terminal_width.setter
    def terminal_width(self, value: int) -> None:
        self.data["terminal_width"] = int(value)

    @property
    def enable_colors(self) -> bool:
        return bool(self.data.get("enable_colors", True))

    @enable_colors.setter
    def enable_colors(self, value: bool) -> None:
        self.data["enable_colors"] = bool(value)

    # -- setup ------------------------------------------------------------
    def __setup(self) -> None:
        # 1. Create the live autosave from the template if it is missing/empty.
        if not self.USER_STATE_PATH.exists() or self.USER_STATE_PATH.stat().st_size == 0:
            default = json.loads(self.DEFAULT_GAME_STATE_PATH.read_text(encoding="utf-8"))
            self.USER_STATE_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")

        # 2. Load the mutable state and merge in the static data files.
        self.data = json.loads(self.USER_STATE_PATH.read_text(encoding="utf-8"))
        self.__load_static()
        self.data.setdefault("running", True)
        self.data.setdefault("enable_colors", True)
        self.data.setdefault("terminal_width", 120)

        self.help_commands[:] = json.loads(
            self.HELP_COMMANDS_PATH.read_text(encoding="utf-8")
        )

        self.normalize_state()
        self.session["duration"]["last_write"] = datetime.now(timezone.utc).isoformat()

    def __load_static(self) -> None:
        self.data["rooms"] = json.loads(
            self.ROOMS_STATE_PATH.read_text(encoding="utf-8")
        )
        self.data["items"] = json.loads(
            self.ITEMS_STATE_PATH.read_text(encoding="utf-8")
        )

    # -- normalisation ----------------------------------------------------
    def __migrate_room_ids(self) -> None:
        """Rename legacy room ids in place (rooms, exits, current room, history)."""
        legacy = {"teacher_room_4": "teachers_room_4"}
        rooms = self.data.get("rooms")
        player = self.data.get("player")
        for old, new in legacy.items():
            if isinstance(rooms, dict):
                if old in rooms:
                    rooms.setdefault(new, rooms.pop(old))
                for room in rooms.values():
                    exits = room.get("exits") if isinstance(room, dict) else None
                    if isinstance(exits, dict):
                        for direction, target in exits.items():
                            if target == old:
                                exits[direction] = new
            if isinstance(player, dict):
                if player.get("current_room") == old:
                    player["current_room"] = new
                for key in ("move", "forward"):
                    history = player.get(key)
                    if isinstance(history, list):
                        player[key] = [
                            new if room_id == old else room_id for room_id in history
                        ]
            if self.data.get("previous_room") == old:
                self.data["previous_room"] = new

    def __backfill_terminal_state(self) -> None:
        """Add terminal item, flag and interactable data missing from older saves."""
        items = self.data.setdefault("items", {})
        if "secret_key" not in items:
            try:
                default_items = json.loads(
                    self.ITEMS_STATE_PATH.read_text(encoding="utf-8")
                )
                default_key = default_items.get("secret_key")
            except (OSError, ValueError):
                default_key = None
            if default_key is not None:
                items["secret_key"] = default_key

        self.data.setdefault("flags", {}).setdefault("tr4_secret_key_copied", False)

        rooms = self.data.get("rooms")
        room = rooms.get("teachers_room_4") if isinstance(rooms, dict) else None
        if isinstance(room, dict):
            room.setdefault("interactables", {}).setdefault(
                "computer", "Nix OS computer"
            )

    def normalize_state(self) -> None:
        """Ensure loaded state uses ``session``, current room ids and current duration schema."""
        if "game_state" in self.data and "session" not in self.data:
            self.data["session"] = self.data.pop("game_state")

        self.__migrate_room_ids()
        self.__backfill_terminal_state()

        session = self.data.setdefault("session", {})
        duration = session.get("duration")
        if isinstance(duration, dict):
            duration["last_write"] = (
                duration.get("last_write") or session.get("timestamp")
            )
            duration["value"] = duration.get("value") or "00:00:00"
            duration["pause"] = duration.get("pause", False)
            return

        session["duration"] = {
            "last_write": session.get("timestamp"),
            "value": duration if isinstance(duration, str) and duration else "00:00:00",
            "pause": False,
        }

    # -- persistence ------------------------------------------------------
    def __snapshot(self) -> dict:
        snapshot = {
            key: self.data[key] for key in self._PERSIST_KEYS if key in self.data
        }
        snapshot["running"] = True
        return snapshot

    def persist(self) -> None:
        tmp = self.USER_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.__snapshot(), indent=4), encoding="utf-8")
        tmp.replace(self.USER_STATE_PATH)

    def reset(self) -> None:
        """Reset the mutable state to the default template."""
        default = json.loads(self.DEFAULT_GAME_STATE_PATH.read_text(encoding="utf-8"))
        self.data.clear()
        self.data.update(default)
        self.__load_static()
        self.data.setdefault("running", True)
        self.data.setdefault("enable_colors", True)
        self.data.setdefault("terminal_width", 120)
        self.normalize_state()

    def auto(self) -> None:
        """Advance clocks, autosave and switch EXPLORATION -> ASSEMBLY when ready."""
        now = datetime.now(timezone.utc).isoformat()
        duration = self.session["duration"]
        elapsed = calculate_duration(duration["last_write"], now)
        duration["last_write"] = now

        if not duration["pause"]:
            duration["value"] = str(elapsed + parse_time_str(duration["value"]))

        if self.session["phase"] == "ASSEMBLY":
            assembly_duration = self.session["phases"]["assembly"].setdefault(
                "duration",
                {"last_write": None, "value": "00:00:00", "pause": False},
            )
            assembly_last_write = assembly_duration["last_write"]
            if not duration["pause"] and assembly_last_write:
                assembly_elapsed = calculate_duration(assembly_last_write, now)
                assembly_duration["value"] = str(
                    assembly_elapsed
                    + parse_time_str(assembly_duration.get("value") or "00:00:00")
                )
            assembly_duration["last_write"] = now

        if not duration["pause"]:
            self.persist()
            if (
                self.workbench["is_ready"]
                and self.session["phase"] == "EXPLORATION"
            ):
                self.session["phase"] = "ASSEMBLY"
                assembly_duration = self.session["phases"]["assembly"].setdefault(
                    "duration",
                    {"last_write": None, "value": "00:00:00", "pause": False},
                )
                assembly_duration["last_write"] = now
                self.session["phases"]["assembly"]["activated"] = True

    def __message(self, text: str | None) -> None:
        if self.render_room is not None:
            self.render_room(text=text)
        elif text:
            out(text)

    def save(self, details: Any = None) -> None:
        """Write the current state to a named slot and register it in the database."""
        if not self.player.get("id"):
            self.__message(
                colorize(
                    "You have to be registered and logged in to save, you can do this at the front desk",
                    self.color.ERROR,
                )
            )
            return None

        filename = details.get("target") if details else None
        if filename is None:
            filename = self.__next_save_slot(self.player["name"])

        filename = re.sub(r"[^\w-]", "", filename.replace(" ", "_"))
        os.makedirs(self.SAVE_DIR, exist_ok=True)
        save_path = os.path.join(self.SAVE_DIR, f"{filename}.json")

        if os.path.exists(save_path):
            self.__message(colorize("An unexpected error occurred", self.color.ERROR))
            return None

        with open(save_path, "w", encoding="utf-8") as handle:
            json.dump(self.__snapshot(), handle, indent=4)
        self._saves.create(filename, self.player["id"])
        self.__message(colorize(f"[system] Game saved to {filename}", self.color.SUCCESS))
        return None

    def list_saves(self) -> tuple:
        """Return the logged-in player's saves as ``(ok, rows_or_message)``.

        Rendering is handled by :meth:`src.engine.Engine.saves`, which also
        prints the section header and each row.
        """
        user_id = self.player.get("id")
        if not user_id:
            return False, "You have to register a profile to view saves. Go to the front desk!"
        user_saves = self._saves.find(user_id)
        if user_saves:
            return True, user_saves

        return False, "You currently have no saved slot linked to your profile"

    def __next_save_slot(self, name: str) -> str:
        prefix = f"{name}_save_slot_"
        numbers = []
        if self.SAVE_DIR.exists():
            for path in self.SAVE_DIR.glob(f"{prefix}*.json"):
                match = re.fullmatch(rf"{re.escape(prefix)}(\d+)\.json", path.name)
                if match:
                    numbers.append(int(match.group(1)))
        return f"{prefix}{max(numbers, default=0) + 1}"

    def spawn(self) -> str:
        """Return a valid room id for the player to start in."""
        room_id = self.player["current_room"]
        if not self.session.get("timestamp"):
            self.session["timestamp"] = datetime.now(timezone.utc).isoformat()
        if not isinstance(room_id, str) or room_id not in self.rooms:
            room_id = next(iter(self.rooms), "lobby")
            self.player["current_room"] = room_id
        return room_id

    def load(self, details: Any) -> None:
        """Replace the active state with a save slot owned by the logged-in player."""
        slot = details["target"].removesuffix(".json")
        if not self.player.get("id"):
            self.__message(
                colorize(
                    text="You have to register to load, go to the front desk",
                    color_code=self.color.RED,
                )
            )
            return None
        if self._saves.find_unique(slot, self.player["id"]) is None:
            self.__message(
                colorize(
                    text=f"You currently do not have any progress saved as '{slot}'",
                    color_code=self.color.RED,
                )
            )
            return None

        save_path = self.SAVE_DIR / f"{slot}.json"
        if not save_path.exists():
            self.__message(
                colorize(
                    text=f"You currently have no saved progress as '{slot}'",
                    color_code=self.color.RED,
                )
            )
            return None

        loaded = json.loads(save_path.read_text(encoding="utf-8"))
        self.data.clear()
        self.data.update(loaded)
        self.__load_static()
        self.data.setdefault("running", True)
        self.data.setdefault("enable_colors", True)
        self.data.setdefault("terminal_width", 120)
        self.normalize_state()
        self.session["duration"]["last_write"] = datetime.now(timezone.utc).isoformat()
        self.__message(colorize(f"Game loaded from {slot}", self.color.BRIGHT_GREEN))
        return None

    def __history_back(self) -> None:
        player = self.player
        history = player.setdefault("move", [])
        if not history:
            self.__message(colorize("You have no previous room to go back to.", self.color.ERROR))
            return None
        previous_room = history[-1]
        if previous_room not in self.rooms:
            self.__message(colorize(f"Unknown destination '{previous_room}'.", self.color.ERROR))
            return None
        history.pop()
        player.setdefault("forward", []).append(player["current_room"])
        player["current_room"] = previous_room
        self.__message(None)
        return None

    def __history_forward(self) -> None:
        player = self.player
        forward = player.setdefault("forward", [])
        if not forward:
            self.__message(colorize("You have no forward room to go to.", self.color.RED))
            return None
        next_room = forward[-1]
        if next_room not in self.rooms:
            self.__message(colorize(f"Unknown destination '{next_room}'.", self.color.ERROR))
            return None
        forward.pop()
        player.setdefault("move", []).append(player["current_room"])
        player["current_room"] = next_room
        self.__message(None)
        return None

    def move(self, details: Any) -> None:
        """Move the player by direction, adjacent room name, or history."""
        destination = details["target"]

        if destination == "back":
            self.__history_back()
            return None
        if destination == "forward":
            self.__history_forward()
            return None

        current_room = self.player["current_room"]
        room_data = self.rooms[current_room]
        exits = room_data["exits"]

        if destination in Alias.ROOM.values():
            target_id = exits.get(destination)
        else:
            target_id = destination if destination in exits.values() else None

        if not target_id:
            adjacent = ", ".join(sorted(set(exits.values()))) or "nowhere"
            self.__message(
                colorize(
                    text=f"You cannot go to {destination} from here. Adjacent: {adjacent}.",
                    color_code=self.color.RED,
                )
            )
            return None

        target_data = self.rooms.get(target_id)
        if not target_data:
            self.__message(
                colorize(
                    text=f"Unknown destination '{target_id}'.",
                    color_code=self.color.RED,
                )
            )
            return None

        requires = target_data.get("requires")
        if requires and requires not in self.player["inventory"]:
            self.__message(
                colorize(
                    text=f"The door is locked. Access requires: {requires}.",
                    color_code=self.color.ERROR,
                )
            )
            return None
        if target_data.get("restricted") and not requires:
            self.__message(colorize(text="The door is locked.", color_code=self.color.ERROR))
            return None

        self.player["forward"].clear()
        self.player["current_room"] = target_id
        self.player["move"].append(current_room)
        self.__message(None)
        return None
