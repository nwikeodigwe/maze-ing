"""Teachers Room 1: the keypad desk that holds the Level-1 staff keycard."""
from src.room import Room


class TeachersRoomOne(Room):
    def __init__(self) -> None:
        super().__init__()

    def use_desk_code(self, item: str, target: str | None = None) -> None:
        """Try ``item`` as the desk code.

        A correct code sets the ``tr1_desk_unlocked`` flag and, if not already
        held, gives the player the desk's reward item. Results are rendered,
        not returned.
        """
        desk = self.rooms["teachers_room_1"]["interactables"]["desk"]
        desk_code = desk["code"]

        if target is not None and target != "desk":
            self.render(text=self.colorize("Nothings happens", color_code=self.color.RED))
            return None

        if self.flags["tr1_desk_unlocked"]:
            self.render(
                text=self.colorize("The desk is already unlocked.", color_code=self.color.GREEN)
            )
            return None

        if item == desk_code.lower():
            self.flags["tr1_desk_unlocked"] = True
            reward = desk["reward"]
            if reward not in self.player["inventory"]:
                self.player["inventory"].append(reward)
                self.render(
                    text=self.colorize(
                        "Keypad clicks green. You've obtained the Level-1 Staff Keycard.",
                        color_code=self.color.GREEN,
                    )
                )
                return None
            self.render(
                text=self.colorize(
                    "You already have a Level-1 Staff keycard.",
                    color_code=self.color.GREEN,
                )
            )
            return None

        self.render(
            text=self.colorize(
                f"Keypad buzzes red: Incorrect code entered.: {item}",
                color_code=self.color.RED,
            )
        )
        return None

    def inspect_desk(self) -> None:
        if not self.flags["tr1_desk_unlocked"]:
            self.render(
                text=self.rooms["teachers_room_1"]["interactables"]["desk"]["hint"]
            )
            return None
        self.render(
            text=self.colorize(
                "The desk drawer is open. You already took the keycard.",
                self.color.SUCCESS,
            )
        )
        return None