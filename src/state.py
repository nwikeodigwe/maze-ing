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
from src.server_state import ServerState
from src.utils.time import calculate_duration, parse_time_str
from src.utils.colors import Colors


class State:
    """In-memory game state plus persistence helpers.

    ``data`` is the single mutable source of truth. Static data (rooms, items)
    is merged in from the default template, and help text is loaded from
    ``data/help.json``, so callers can use either object attributes
    (``state.player``) or mapping access (``state["player"]``).
    """

    _PERSIST_KEYS = (
        "player",
        "rooms",
        "items",
        "server",
        "workbench",
        "flags",
        "session",
        "running",
        "enable_colors",
        "terminal_width",
        "inventory_capacity"
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
    def server(self) -> ServerState:
        """The Lab D 2001 server-provisioning challenge state."""
        if "server" not in self.data:
            self.data["server"] = ServerState.default()
        return ServerState(self.data["server"])

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

    @property
    def inventory_capacity(self) -> int:
        return int(self.data.get("inventory_capacity", 11))

    @inventory_capacity.setter
    def inventory_capacity(self, value: int) -> None:
        self.data["inventory_capacity"] = int(value)

    # -- setup ------------------------------------------------------------
    def __setup(self) -> None:
        # 1. Create the live autosave from the template if it is missing/empty.
        if not self.USER_STATE_PATH.exists() or self.USER_STATE_PATH.stat().st_size == 0:
            default = json.loads(self.DEFAULT_GAME_STATE_PATH.read_text(encoding="utf-8"))
            self.USER_STATE_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")

        # 2. Load the mutable state and merge in the static data files.
        self.data = json.loads(self.USER_STATE_PATH.read_text(encoding="utf-8"))
        if not self.data["session"]["timestamp"]:
            self.data["session"]["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.__load_static()

        self.help_commands[:] = json.loads(
            self.HELP_COMMANDS_PATH.read_text(encoding="utf-8")
        )

        self.normalize_state()
        self.session["duration"]["last_write"] = datetime.now(timezone.utc).isoformat()

    def __load_static(self) -> None:
        """Fill rooms and items from the default template when absent.

        Rooms and items are persisted in ``user.json`` so progression survives a
        reload; they are only pulled from ``data/default.json`` for fresh or
        pre-persistence saves that do not carry them yet.
        """
        default = json.loads(self.DEFAULT_GAME_STATE_PATH.read_text(encoding="utf-8"))
        if "rooms" not in self.data:
            self.data["rooms"] = default.get("rooms", {})
        if "items" not in self.data:
            self.data["items"] = default.get("items", {})
        if "server" not in self.data:
            self.data["server"] = default.get("server", ServerState.default())
        items = self.data.get("items", {})
        # Required assembly parts are derived from the item flags, so the
        # workbench always stays in sync with the item definitions.
        workbench = self.data.setdefault("workbench", {})
        workbench["required_parts"] = [
            item_id for item_id, meta in items.items() if meta.get("is_assembly_part")
        ]

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
        """Add flag and interactable data missing from older saves."""
        default = json.loads(self.DEFAULT_GAME_STATE_PATH.read_text(encoding="utf-8"))
        for flag, value in default.get("flags", {}).items():
            self.data.setdefault("flags", {}).setdefault(flag, value)
        for item_id, meta in default.get("items", {}).items():
            self.data.setdefault("items", {}).setdefault(item_id, meta)

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


    def save(self, details: Any = None) -> tuple:
        """Write the current state to a named slot and register it in the database."""
        if not self.player.get("id"):
            return False, "You have to be registered and logged in to save, you can do this at the front desk"

        filename = details.get("target") if details else None
        if filename is None:
            filename = self.__next_save_slot(self.player["name"])

        filename = re.sub(r"[^\w-]", "", filename.replace(" ", "_"))
        os.makedirs(self.SAVE_DIR, exist_ok=True)
        save_path = os.path.join(self.SAVE_DIR, f"{filename}.json")

        if os.path.exists(save_path):
            return False, "An unexpected error occurred"

        with open(save_path, "w", encoding="utf-8") as handle:
            json.dump(self.__snapshot(), handle, indent=4)
        self._saves.create(filename, self.player["id"])
        return True, f"[system] Game saved to {filename}"

    def list_saves(self) -> tuple:
        """Return the logged-in player's saves as ``(ok, rows_or_message)``.

        Rendering is handled by :meth:`src.engine.Engine.saves`, which also
        prints the section header and each row.
        """
        user_id = self.player.get("id")
        if not user_id:
            return False, "You have to register a profile to view saves. Go to the front desk!"
        rows = self._saves.find().where(user_id=user_id).all()
        if rows:
            return True, rows

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

    def load(self, details: Any) -> tuple:
        """Replace the active state with a save slot owned by the logged-in player."""
        slot = details["target"].removesuffix(".json")
        if not self.player.get("id"):
            return False, "You have to register to load, go to the front desk"

        if self._saves.find().where(slot=slot, user_id=self.player["id"]).first() is None:
            return False, f"You currently do not have any progress saved as '{slot}'"

        save_path = self.SAVE_DIR / f"{slot}.json"
        if not save_path.exists():
            return False, f"You currently have no saved progress as '{slot}'"

        loaded = json.loads(save_path.read_text(encoding="utf-8"))
        self.data.clear()
        self.data.update(loaded)
        self.__load_static()
        self.data.setdefault("running", True)
        self.data.setdefault("enable_colors", True)
        self.data.setdefault("terminal_width", 120)
        self.normalize_state()
        self.session["duration"]["last_write"] = datetime.now(timezone.utc).isoformat()
        return True, f"Game loaded from {slot}"

    def __history_back(self) -> tuple:
        player = self.player
        history = player.setdefault("move", [])
        if not history:
            return False, "You have no previous room to go back to."
        previous_room = history[-1]
        if previous_room not in self.rooms:
            return False, f"Unknown destination '{previous_room}'."
        history.pop()
        player.setdefault("forward", []).append(player["current_room"])
        player["current_room"] = previous_room
        return True, None

    def __history_forward(self) -> tuple:
        player = self.player
        forward = player.setdefault("forward", [])
        if not forward:
            return False, "You have no forward room to go to."
        next_room = forward[-1]
        if next_room not in self.rooms:
            return False, f"Unknown destination '{next_room}'."
        forward.pop()
        player.setdefault("move", []).append(player["current_room"])
        player["current_room"] = next_room
        return True, None

    def move(self, details: Any) -> tuple:
        """Move the player by direction, adjacent room name, or history."""
        destination = details["target"]

        if destination == "back":
            return self.__history_back()
        if destination == "forward":
            return self.__history_forward()

        current_room = self.player["current_room"]
        room_data = self.rooms[current_room]
        exits = room_data["exits"]

        if destination in Alias.ROOM.values():
            target_id = exits.get(destination)
        else:
            target_id = destination if destination in exits.values() else None

        if not target_id:
            adjacent = ", ".join(sorted(set(exits.values()))) or "nowhere"

            return False, f"You cannot go to {destination} from here. Adjacent: {adjacent}."

        target_data = self.rooms.get(target_id)
        if not target_data:
            return False, f"Unknown destination '{target_id}'."

        requires = target_data.get("requires") or []
        if isinstance(requires, str):
            requires = [requires]

        if requires and not all(rid in self.player["inventory"] for rid in requires):
            names = ", ".join(self.items[rid]["name"] for rid in requires)
            return False, f"The door is locked. Access requires: {names}."

        if target_data.get("restricted") and not requires:
            return False, "The door is locked."

        self.player["forward"].clear()
        self.player["current_room"] = target_id
        self.player["move"].append(current_room)
        return True, None
