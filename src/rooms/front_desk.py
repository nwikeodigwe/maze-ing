from src.room import Room


class FrontDesk(Room):
    def inspect_receptionist(self):
        receptionist = self.rooms["front_desk"]["interactables"]["receptionist"]
        self.render(text=receptionist)
        return None