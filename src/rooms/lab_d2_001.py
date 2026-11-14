import time

from src.room import Room
from src.utils.loader import loader
from src.utils.shell import ServerShell


class LabD2001(Room):
    def __init__(self):
        super().__init__()

    def _award_provisioning_certificate(self) -> None:
        """Mark the challenge complete and grant the certificate once."""
        self.flags["lab_server_provisioned"] = True
        if "server_provisioning_certificate" in self.player["inventory"]:
            return
        self.player["inventory"].append("server_provisioning_certificate")
        name = self.items["server_provisioning_certificate"]["name"]
        self.out(self.colorize(text=f"{name} added to your inventory!", color_code=self.color.SUCCESS))

    def inspect_server(self) -> None:
        """Open the lab workstation terminal and run the provisioning challenge.

        The game clock is paused for the whole session and rebased on exit, so
        time spent in the terminal is never charged to the player.
        """
        loader(
            loading_time=1.2,
            label="Booting up workstation...",
            mode="LOADER",
        )
        time.sleep(1)
        self.session["duration"]["pause"] = True
        try:
            self.clear()
            shell = ServerShell(self.state.server)
            while True:
                try:
                    raw = input(shell.prompt + " ")
                except (EOFError, KeyboardInterrupt):
                    break
                result = shell.execute(raw)
                if result.output:
                    print(result.output)
                if result.prompt:
                    try:
                        answer = input(result.prompt)
                    except (EOFError, KeyboardInterrupt):
                        break
                    result = shell.answer(answer)
                    if result.output:
                        print(result.output)
                if result.clear_requested:
                    self.clear()
                if result.exit_requested:
                    break
        finally:
            # auto() rebases the timestamp while the clock is still paused, so
            # the time spent in the terminal is discarded rather than charged.
            self.auto()
            self.session["duration"]["pause"] = False
            self.clear()
            self.render()
        if self.state.server.complete:
            self._award_provisioning_certificate()
            self.out(
                self.colorize(
                    text=(
                        "Server Provisioning Complete - the robot's neural link "
                        "can come up."
                    ),
                    color_code=self.color.SUCCESS,
                )
            )
        return None
