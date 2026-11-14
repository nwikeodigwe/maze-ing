from src.room import Room


class FrontDesk(Room):
    def inspect_receptionist(self):
        interactables = self.rooms["front_desk"].get("interactables", {})
        text = interactables.get("receptionist") or interactables.get("guide", "")
        self.render(text=text)
        return None