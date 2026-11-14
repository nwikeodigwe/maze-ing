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
        self.out(
            self.colorize(
                text=f"{name} added to your inventory!",
                color_code=self.color.SUCCESS,
            )
        )

    def _run_shell(self, shell: ServerShell) -> None:
        """Read commands from the player and feed them to the shell.

        The shell may ask follow-up questions of its own; each one is answered
        until the shell has no prompt left.

        Args:
            shell: The shell session to drive.
        """
        while True:
            try:
                raw = input(shell.prompt + " ")
            except (EOFError, KeyboardInterrupt):
                return
            result = shell.execute(raw)
            while result.prompt:
                if result.output:
                    self.out(result.output)
                try:
                    answer = input(result.prompt)
                except (EOFError, KeyboardInterrupt):
                    return
                result = shell.answer(answer)
            if result.output:
                self.out(result.output)
            if result.clear_requested:
                self.clear()
            if result.exit_requested:
                return

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
            self._run_shell(ServerShell(self.state.server))
        finally:
            # auto() rebases the timestamp while the clock is still paused, so
            # the time spent in the terminal is discarded rather than charged.
            self.auto()
            self.session["duration"]["pause"] = False
            self.persist()
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
