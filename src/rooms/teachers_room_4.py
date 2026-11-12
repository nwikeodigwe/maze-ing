"""NixOS terminal challenge in Teacher Room 4.

Inspecting the room computer boots a virtual NixOS shell where the player
explores an in-memory filesystem and hunts for a hidden secret file. Reading
that file awards ``secret_key`` to the inventory exactly once and sets the
``tr4_secret_key_copied`` flag.
"""
import time

from rich.console import Console
from rich.text import Text

from src.room import Room
from src.utils.display import clear
from src.utils.shell import VirtualShell
from src.utils.loader import loader
from src.assets.nixos import nixos as nixos_logo
from src.utils.colors import Colors

# Boot log lines shown by the loader before the terminal opens.
computer_sequence = [
    "systemd-boot → NixOS Generation 42",
    "<<< NixOS Stage 1 >>> loading kernel modules",
    "LUKS unlock… skipped (no secrets here. Probably.)",
    "Mounting /nix/store from /dev/sda1",
    "Stage 2 activation: /etc, users, secrets",
    "starting systemd... (PID 1)",
    "Reached graphical.target",
]

# Absolute virtual path of the only file that grants the secret key.
SECRET_PATH = "/home/teacher/.secret/super_secret_file.txt"

# Virtual filesystem: dicts are directories, strings are file contents.
FILESYSTEM = {
    "etc": {
        "hostname": "teacher-pc\n",
        "passwd": "root:x:0:0:root:/root:/bin/bash\nteacher:x:1000:100:Teacher:/home/teacher:/bin/bash\n",
        "nixos": {
            "configuration.nix": (
                "{ config, pkgs, ... }:\n{\n  networking.hostName = \"teacher-pc\";\n"
                "  users.users.teacher.isNormalUser = true;\n  system.stateVersion = \"26.05\";\n}\n"
            ),
        },
    },
    "home": {
        "teacher": {
            "Documents": {
                "grading_notes.txt": "Grade fairly. Coffee first.\n",
                "exam_draft.txt": "Question 1: Why is the maze so confusing?\n",
                ".notes.txt": (
                    "I moved the schematic somewhere out of sight.\n"
                    "Hidden things tend to live in hidden places.\n"
                ),
            },
            "Downloads": {
                "lecture_slides.pdf": "[binary data omitted]\n",
            },
            "Projects": {
                "maze_generator": {
                    "README.md": "A tiny maze generator. Work in progress.\n",
                },
            },
            ".config": {
                "nixpkgs": {"config.nix": "{ allowUnfree = true; }\n"},
            },
            ".secret": {
                "super_secret_file.txt": (
                    "Congratulations!\n"
                    "You found the A-maze-ing Delft schematic.\n"
                    "The Secret Key has been copied to your inventory.\n"
                ),
            },
            ".bashrc": "# ~/.bashrc\nalias ll='ls -l'\n",
            "README.txt": (
                "Welcome to teacher-pc. Type 'help' to see the available commands.\n"
                "Tip: not every file shows up in a plain ls. Try 'ls -a' or 'find'.\n"
            ),
        },
    },
    "nix": {
        "store": {
            "nixos-system": {
                "README": "This is the NixOS system closure. Nothing to see here.\n",
            },
        },
    },
    "var": {
        "log": {
            "nixos.log": "activating the configuration...\nsetting up /etc...\nsystem activated.\n",
        },
    },
}

# Shared console used for boot output and the default shell writer.
console = Console()
color = Colors()


def _prompt_text(shell: VirtualShell) -> str:
    """Build the two-line colored terminal prompt.

    Args:
        shell: Shell providing the user, host, and display directory.

    Returns:
        The prompt string passed to the input reader.
    """
    top_line = (
        f"{color.CYAN}┌──({color.BLUE}{shell.user}㉿{shell.hostname}"
        f"{color.CYAN})-[{color.BOLD}{shell.display_cwd}{color.RESET}{color.CYAN}]"
        f"{color.RESET}"
    )
    bottom_line = f"{color.CYAN}└─{color.BLUE}${color.RESET} "
    return f"{top_line}\n{bottom_line}"

class TeachersRoomFour(Room):
    def __init__(self) -> None:
        super().__init__()

    def _award_secret_key(self, write_output=None) -> None:
        """Grant the secret key on first read of the secret file.

        Always sets the ``tr4_secret_key_copied`` flag; appends ``secret_key``
        to the inventory only when it is not already there.

        Args:
            write_output: Callable receiving the status message. Defaults to
                the module console printer.
        """
        write_output = write_output or console.print
        inventory = self.player["inventory"]
        self.flags["tr4_secret_key_copied"] = True
        if "secret_key" in inventory:
            write_output("[dim]The Secret Key is already in your inventory.[/]")
            return
        inventory.append("secret_key")
        name = self.items.get("secret_key", {}).get("name", "Secret Key")
        write_output(f"[bold green]{name} added to your inventory![/]")

    def run_shell(self, shell: VirtualShell, read_input=input, write_output=None,
                  clear_screen=clear) -> None:
        """Run the interactive read-execute loop until exit or interrupt.

        Command output is printed literally so shell text is never interpreted
        as Rich markup. Reading the secret file triggers the key reward.

        Args:
            shell: Virtual shell executing each input line.
            read_input: Callable reading one line with the prompt.
            write_output: Callable receiving output text. Defaults to the
                module console printer.
            clear_screen: Callable clearing the screen on ``clear``.

        Returns:
            None. Terminates on ``exit`` or on EOF/KeyboardInterrupt.
        """
        write_output = write_output or console.print
        while True:
            try:
                raw = read_input(_prompt_text(shell))
            except (EOFError, KeyboardInterrupt):
                write_output("")
                break
            result = shell.execute(raw)
            if result.clear_requested:
                clear_screen()
            if result.output:
                write_output(Text(result.output))
            if SECRET_PATH in result.read_paths:
                self._award_secret_key(write_output)
            if result.exit_requested:
                break

    def inspect_note(self) -> None:
        """Handle inspecting note in teachers room 4"""
        current_room = self.player["current_room"]
        desc = self.rooms[current_room]["interactables"]["note"]
        self.render(desc)
        return None

    def inspect_computer(self) -> None:
        """Boot the NixOS computer and open the terminal session.

        Pauses the game timer, plays the boot sequence and logo, runs the
        shell, then rebases the timer while still paused so terminal time is
        never charged before resuming, clearing, and re-rendering the room.

        Returns:
            None.
        """
        self.session["duration"]["pause"] = True
        try:
            loader(
                loading_time=1.2,
                label="Booting up the computer...",
                console=console,
                mode="PROGRESS",
                sequence=computer_sequence,
            )
            time.sleep(1)
            clear()
            console.print(nixos_logo())
            time.sleep(2)
            clear()
            console.print(
                "Viola! you are half way in! Now explore the file system to see if you find anything interesting. "
                "Type 'help' to list the available commands."
            )
            time.sleep(1)
            console.print("[bold green]NIXOS // teacher-pc[/]")
            console.print("[dim]NixOS 26.05 (Linux 6.12.1)[/]")
            self.run_shell(VirtualShell(FILESYSTEM))
        finally:
            self.auto()
            self.session["duration"]["pause"] = False
            clear()
            self.render()

