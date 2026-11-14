"""Lab D 2001: the workbench where the robot is assembled and activated.

Installing every required part flips the phase to ``ASSEMBLY``; :func:`activate` then asks for the Wi-Fi password and
a robot name, records the player's score on the scoreboard and switches the game to the ``CHAT`` phase.
"""

import time

from src.models.scoreboard import Scoreboard
from src.room import Room
from src.utils.time import parse_time_str
from datetime import timedelta

BASE_SCORE = 1000
EXPLORATION_POINTS_PER_MINUTE = 12
ASSEMBLY_POINTS_PER_MINUTE = 4

<<<<<<<< HEAD:src/rooms/lab.py
class Lab(Room):
========
class LabD2002(Room):
>>>>>>>> 0cf63c936f8a566f8cf5b3ac3ec52fdcb23745a8:src/rooms/lab_d2_002.py
    def __init__(self) -> None:
        super().__init__()
        self.scoreboard = Scoreboard()

    def __calculate_score(self, exploration: timedelta, assembly: timedelta) -> int:
        """Return a 0-1000 score; longer exploration and assembly times reduce it.

        Args:
            exploration: Time spent in the exploration phase.
            assembly: Time spent in the assembly phase.

        Returns:
            ``BASE_SCORE`` minus the weighted time penalty, rounded and never below 0.
        """
        penalty = (
                exploration.total_seconds() / 60 * EXPLORATION_POINTS_PER_MINUTE
                + assembly.total_seconds() / 60 * ASSEMBLY_POINTS_PER_MINUTE
        )
        # Clamp so very slow runs bottom out at 0 instead of going negative.
        return max(0, round(BASE_SCORE - penalty))

    def activate(self) -> None:
        """Run the activation sequence once all parts are installed.

        Asks for the Wi-Fi password and a robot name, and records a scoreboard row if the player is registered. Phase is
        set to ``CHAT`` only after a correct password; a wrong password or missing parts just re-renders the workbench.
        Blocks for two seconds during the "initialising" splash.
        """
        required_parts = self.workbench["required_parts"]
        installed_parts = self.workbench["installed_parts"]
        missing = len(required_parts) - len(installed_parts)
        if missing > 0:
            self.render_workbench(
                self.colorize(
                    text=f"Assembly incomplete. {missing} part(s) missing.",
                    color_code=self.color.ERROR,
                )
            )
            return None
        if not self.flags.get("lab_server_provisioned"):
            self.render_workbench(
                self.colorize(
                    text=(
                        "The robot's neural link needs the maze-server backend "
                        "provisioned first. Finish the server configuration in "
                        "Lab D 2001."
                    ),
                    color_code=self.color.ERROR,
                )
            )
            return None
        self.render_workbench(text="Enter wifi password to continue.")
        password = self.prompt()
        self.clear()
        if password != self.session["phases"]["assembly"]["wifi_password"]:
            self.render_workbench(self.colorize(text="Invalid wifi credentials.", color_code=self.color.ERROR))
            return None
        self.render_workbench(
            text=f"Give your robot a name. Default name is {self.session['phases']['chat']['robot']['name']}."
        )
        name = self.prompt()

        user_id = self.player["id"]
        if user_id:
            total = parse_time_str(self.session["duration"]["value"])
            assembly = parse_time_str(
                self.session["phases"]["assembly"]["duration"]["value"]
            )
            # The total clock runs through both phases, so exploration time is whatever the assembly timer excludes.
            exploration = total - assembly
            # Guard against division by zero when computing the average time per room.
            room_count = len(self.rooms) or 1
            avg_room_time = timedelta(seconds=(exploration // room_count).seconds)
            data = {
                "user_id":user_id,
                "score": self.__calculate_score(exploration, assembly),
                "avg_room_time":str(avg_room_time),
                "exploration_time": str(exploration),
                "assembly_time":str(assembly)
            }
            self.scoreboard.create(data)

        robot = self.session["phases"]["chat"]["robot"]
        if name and name.strip():
            robot["name"] = name.strip()
        self.clear()
        self.render(self.colorize(text=f"INITIALIZING {robot['name'].upper()}...", color_code=self.color.BRIGHT_GREEN))
        time.sleep(2)
        self.session["phase"] = "CHAT"
        return None

    def render_workbench(self, text: str | None = None) -> None:
        """Display the workbench: installed vs. missing parts and what to do next.

        Args:
            text: Optional message shown under the part list (feedback from the last action, or a custom activation hint
                once all parts are installed).
        """
        installed_parts = self.workbench["installed_parts"]
        required_parts = self.workbench["required_parts"]

        self.draw_line("═")
        self.out(
            self.colorize(
                text=f"[{self.session['phase']}]", color_code=self.color.BRIGHT_YELLOW
            )
        )
        self.out(
            self.colorize(
                text="Lab D2 002 WORKBENCH", color_code=self.color.BRIGHT_MAGENTA + self.color.BOLD
            )
        )
        self.out(
            self.colorize(
                text=f"[{self.session['duration']['value']}]", color_code=self.color.DIM
            )
        )
        self.draw_line("═")
        self.out(
            f"Progress: {len(installed_parts)} / {len(required_parts)} components installed.\n"
            )

        for part in required_parts:
            item_data = self.items[part]

            if part in installed_parts:
                status = self.colorize(
                    text="[ INSTALLED ]", color_code=self.color.BRIGHT_GREEN + self.color.BOLD
                )
            else:
                status = self.colorize(text="[ MISSING   ]", color_code=self.color.RED + self.color.DIM)

            self.out(f" {status} - {item_data['name']}")

        self.out()
        if len(installed_parts) == len(required_parts) and self.session[
            "phase"] != "CHAT":
            command = text if text else "Type 'activate' or 'power on' to start the neural link."
            self.out(
                self.colorize(
                    text=">> ALL CORE COMPONENTS INSTALLED <<",
                    color_code=self.color.BRIGHT_GREEN + self.color.BOLD
                )
            )
            self.out(
                self.colorize(text=
                    command,
                    color_code=self.color.BRIGHT_YELLOW
                )
            )
        else:
            remaining = len(required_parts) - len(installed_parts)
            if text:
                self.out(text)
            self.out(
                self.colorize(
                    text=f"Locate remaining {remaining} part(s) to complete assembly.",
                    color_code=self.color.DIM
                )
            )
        return

    def use_on_workbench(self, item: str) -> None:
        """Install an inventory item on the workbench.

        Rejects unknown items, items not carried, non-components and already installed parts, re-showing the
        workbench with an error. Installing the last required part sets ``workbench["is_ready"]`` and moves the phase
        to ``ASSEMBLY``.

        Args:
            item: Item id the player wants to install.
        """

        required_parts = self.workbench["required_parts"]
        installed_parts = self.workbench["installed_parts"]
        inventory = self.player["inventory"]
        try:
            item_data = self.items[item]
        except KeyError:
            self.render_workbench(
                text=self.colorize(f"'{item}' is not a workbench component.", color_code=self.color.ERROR)
                )
            return None

        if item not in self.player["inventory"]:
            self.render_workbench(
                text=self.colorize(
                    f"You currently do not have {item_data['name']} in your inventory.",
                    color_code=self.color.ERROR
                    )
            )
            return None

        if item not in required_parts:
            self.render_workbench(
                text=self.colorize(
                    f"'{item_data['name']}' is not a workbench component.",
                    color_code=self.color.ERROR
                )
            )
            return None
        if item in installed_parts:
            self.render_workbench(
                text=self.colorize(
                    f"'{item_data['name']}' is already installed.", color_code=self.color.ERROR
                )
            )
            return None
        inventory.remove(item)
        installed_parts.append(item)

        # Last part installed: the workbench is ready and the phase advances immediately.
        if len(installed_parts) >= len(required_parts):
            self.workbench["is_ready"] = True
            self.session["phase"] = "ASSEMBLY"
            self.render_workbench(
                text=self.colorize(
                    f"{item_data['name']} installed. ALL COMPONENTS INSTALLED — type 'activate'.",
                    color_code=self.color.ERROR
                )
            )
            return None
        self.render_workbench(
            text=self.colorize(
                f"{item_data['name']} installed ({len(installed_parts)}/{len(required_parts)}).",
                color_code=self.color.ERROR
            )
        )
        return None

