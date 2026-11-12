import random
import re

from src.alias import Alias
from src.models.user import User


class Parser(Alias):
    def __init__(self):
        super().__init__()
        self.user = User()


    def __generate_username(self) -> str:
        """Generates a random username and verifies it does not exist in the database."""

        prefixes = ["Operator", "Cyber", "Null", "Cipher", "Agent","Ghost", "Vector","Node"]
        callsigns = ["Aegis", "Vex", "Echo", "Kilo", "Zero", "Nexus","Drift", "Sol"]

        while True:
            # 1. Build a candidate username
            prefix = random.choice(prefixes)
            callsign = random.choice(callsigns)
            suffix = random.randint(100, 999)
            candidate = f"{prefix}_{callsign}_{suffix}"

            # 2. Check SQLite DB for existence
            if self.user.find().where(name=candidate).first() is None:
                return candidate


    def normalize_room_key(self, raw: str) -> str:
        """Normalize a room reference for alias lookup.

        Args:
            raw: User text such as ``"Lab_D2_001"``.

        Returns:
            Lower-cased text with underscores turned into spaces and whitespace collapsed to single spaces.
        """
        return " ".join(raw.strip().lower().replace("_", " ").split())

    def resolve_room_target(self, raw: str) -> str:
        """Resolve user input to a direction (``"north"``) or room id (``"lobby"``).

        Direction aliases take precedence; otherwise the room name/alias map is consulted (also with spaces turned into
        underscores); unknown input falls back to the normalised string with underscores, which the caller then fails to
        find in the exits.

        Args:
            raw: User text naming a direction or room.

        Returns:
            A canonical direction, ``"back"``/``"forward"``, a room id, or the underscored fallback string.
        """
        key = self.normalize_room_key(raw)
        if key in self.ROOM:
            return self.ROOM[key]
        if key in self.ROOMS:
            return self.ROOMS[key]
        underscored = key.replace(" ", "_")
        if underscored in self.ROOMS:
            return self.ROOMS[underscored]
        return underscored

    def parse(self, raw_input: str) -> tuple[str, dict]:
        """Parse a raw command line.

        See the module docstring for the full result contract.

        Args:
            raw_input: The line typed by the player.

        Returns:
            ``(verb, details)``. ``verb`` is a canonical verb or one of ``"EMPTY"``, ``"UNKNOWN"``, ``"INVALID"``.
            ``details`` may contain:

            * ``"target"``: primary target (room, item, object, slot, user name or code).
            * ``"indirect"``: secondary target for ``use`` (e.g. ``"workbench"``), or ``None``.
            * ``"raw"``: unmodified argument string.
            * ``"message"``: player-facing hint (``INVALID`` only).
        """
        cleaned = raw_input.strip().lower()
        if not cleaned:
            return "EMPTY", {}

        tokens = cleaned.split()
        first_token = tokens[0]

        # Case 1: Single-token movement ("n", "south", "lobby", "d2015").
        if len(tokens) == 1 and (
                first_token in self.ROOM or first_token in self.ROOMS
        ):
            return "go", {"target": self.resolve_room_target(cleaned), "raw": cleaned}

        # Resolve primary verb. Prefer an exact multi-word alias when it maps to
        # a different action than the first token (e.g. "check status").
        # A multi-word alias (e.g. "check status") beats the first token alone when it maps to a different verb;
        # in that case the remaining words are treated as part of the alias, not as arguments.
        verb = self.VERBS.get(first_token)
        exact_verb = self.VERBS.get(cleaned) if " " in cleaned else None
        if exact_verb is not None and exact_verb != verb:
            verb = exact_verb
            args = []
            arg_str = ""
        elif verb:
            args = tokens[1:]
            arg_str = " ".join(args)
        else:
            return "UNKNOWN", {"raw": raw_input}

        if verb == "look":
            return "look", {"raw": arg_str}

        if verb == "inventory":
            return "inventory", {"raw": arg_str}

        if verb == "help":
            return "help", {"raw": arg_str}

        if verb == "scoreboard":
            return "scoreboard", {"raw": arg_str}

        if verb == "status":
            return "status", {"raw": arg_str}

        if verb == "clear":
            return "clear", {"raw": arg_str}

        if verb == "register":
            # Registering without a name picks a random unused one (this hits the database).
            username = args[0] if args else self.__generate_username()
            return "register", {"target": username, "raw": arg_str}

        if verb == "login":
            if not args:
                return ("INVALID", {
                    "message": "You have to enter a valid username (e.g., 'login user1')."})
            username = args[0]
            return "login", {"target": username, "raw": arg_str}

        if verb == "logout":
            return "logout", {"raw": arg_str}

        if verb == "save":
            slot = args[0] if args else None
            return "save", {"target": slot, "raw": arg_str}

        if verb == "saves":
            return "saves", {"raw": arg_str}

        if verb == "load":
            if not args:
                return ("INVALID", {
                    "message": "Enter a valid slot to load (e.g., 'load user_slot_1')."})
            slot = args[0]
            return "load", {"target": slot, "raw": arg_str}

        if verb == "restart":
            return "restart", {"raw": arg_str}

        if verb == "quit":
            return "quit", {"raw": arg_str}

        if verb == "activate":
            return "activate", {"raw": arg_str}

        if verb == "go":
            if not args:
                return ("INVALID", {
                    "message": "Go where? Specify a direction (north, south, east, west) or room name."})
            target = self.resolve_room_target(arg_str)
            return "go", {"target": target, "raw": arg_str}

        if verb == "inspect":
            if not args:
                return ("INVALID", {
                    "message": "Inspect what? Specify an item or object (e.g., 'inspect desk')."})
            target_id = self.ITEMS.get(arg_str, arg_str)
            return "inspect", {"target": target_id, "raw": arg_str}

        if verb == "take":
            if not args:
                return ("INVALID", {
                    "message": "Take what? Specify an item (e.g., 'take battery_pack')."})
            # Handle "pick up <item>"
            # "pick up <item>" is a two-word verb: drop the "up" so only the item name is looked up.
            if first_token == "pick" and args and args[0] == "up":
                item_tokens = args[1:]
                arg_str = " ".join(item_tokens)
            target_id = self.ITEMS.get(arg_str, arg_str)
            return "take", {"target": target_id, "raw": arg_str}

        if verb == "drop":
            if not args:
                return ("INVALID", {
                    "message": "drop what? Specify an item to drop (e.g., 'drop battery_pack')."})
            target_id = self.ITEMS.get(arg_str, arg_str)
            return "drop", {"target": target_id, "raw": arg_str}

        if verb == "use":
            if not args:
                return ("INVALID", {
                    "message": "Use what? Syntax: 'use <item>' or 'use <item> on <target>'."})

            # Pattern matching for "use <item> on/with <target>" or "put <item> on <workbench>"
            # Lazy first group splits at the FIRST preposition: "use key on door with lock" -> item "key",
            # indirect "door with lock".
            use_pattern = re.match(r"^(.*?)\s+(?:on|with|in|onto)\s+(.*)$", arg_str)
            if use_pattern:
                item_raw = use_pattern.group(1).strip()
                indirect_raw = use_pattern.group(2).strip()
                item_id = self.ITEMS.get(item_raw, item_raw)
                return ("use",
                        {"target": item_id, "indirect": indirect_raw, "raw": arg_str})
            else:
                item_id = self.ITEMS.get(arg_str, arg_str)
                return "use", {"target": item_id, "indirect": None, "raw": arg_str}

        return "UNKNOWN", {"raw": raw_input}