"""Teachers Room 2."""
from src.room import Room


class TeachersRoomTwo(Room):
    def inspect_whiteboard(self) -> None:
        self.flags["tr2_whiteboard_inspected"] = True
        whiteboard = self.rooms["teachers_room_2"]["interactables"]["whiteboard"]
        self.render(text=whiteboard)
        return None