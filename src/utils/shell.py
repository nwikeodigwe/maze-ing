"""Virtual shell engine for the Teacher Room 4 NixOS terminal.

Parses and executes a small set of shell-like commands against an in-memory
filesystem tree where a ``dict`` represents a directory and a ``str`` holds
file contents. The engine is pure: it never touches game state, display code,
the real filesystem, the network, or the host operating system, and
:meth:`VirtualShell.execute` never raises for user input.
"""

import fnmatch
import posixpath
import shlex
from collections.abc import Callable
from dataclasses import dataclass

from src.server_state import (
    LOCAL_MACHINE,
    LOCAL_USER,
    SERVER_HOSTNAME,
    SERVER_IP,
    ServerState,
)

HELP_TEXT = """Available commands:
  ls [-a] [-l] [path...]   list directory contents
  cd [path]                change directory
  pwd                      print the working directory
  cat <file...>            print file contents
  find [path]              search for files
  tree [path]              show a directory tree
  clear                    clear the screen
  whoami                   print the current user
  exit                     leave the terminal
  help                     show this help"""


@dataclass(frozen=True)
class ShellResult:
    """Outcome of executing a single shell command.

    Attributes:
        output: Text to print for the command. Empty when the command
            produces no visible output.
        exit_requested: True when the shell loop should terminate.
        clear_requested: True when the screen should be cleared.
        read_paths: Absolute virtual paths of files whose contents were
            printed, used by callers to trigger read-based rewards.
        prompt: Text of a sub-prompt the shell is waiting on. The caller
            reads a line and passes it back to the shell.
    """

    output: str = ""
    exit_requested: bool = False
    clear_requested: bool = False
    read_paths: tuple[str, ...] = ()
    prompt: str | None = None


class VirtualShell:
    """Stateful shell bound to one in-memory filesystem tree.

    Attributes:
        filesystem: Nested dicts (directories) and strings (file contents)
            forming the virtual filesystem.
        cwd: Absolute path of the current working directory.
        home: Absolute path treated as the home directory for ``~``.
        user: Login name shown in the prompt.
        hostname: Host name shown in the prompt.
    """

    def __init__(
        self,
        filesystem: dict,
        cwd: str = "/home/teacher",
        home: str = "/home/teacher",
        user: str = "teacher",
        hostname: str = "teacher-pc",
    ):
        """Bind the shell to a filesystem with an initial identity.

        Args:
            filesystem: Virtual filesystem tree of nested dicts and strings.
            cwd: Starting working directory.
            home: Home directory used for ``~`` expansion and display.
            user: Login name shown in the prompt.
            hostname: Host name shown in the prompt.
        """
        self.filesystem = filesystem
        self.cwd = cwd
        self.home = home
        self.user = user
        self.hostname = hostname

    @property
    def display_cwd(self) -> str:
        """Working directory with the home prefix shortened to ``~``.

        Returns:
            ``~`` at home, ``~/<suffix>`` below home, otherwise the
            absolute path.
        """
        if self.cwd == self.home:
            return "~"
        if self.cwd.startswith(self.home + "/"):
            return "~" + self.cwd[len(self.home) :]
        return self.cwd

    @property
    def prompt(self) -> str:
        """Bash-style prompt for the current user, host, and directory.

        Returns:
            A string like ``teacher@teacher-pc:~$``.
        """
        return f"{self.user}@{self.hostname}:{self.display_cwd}$"

    def execute(self, command: str) -> ShellResult:
        """Parse and run one command line against the virtual filesystem.

        Args:
            command: Raw input line, parsed with :func:`shlex.split`.

        Returns:
            The command outcome. Malformed input such as unmatched quotes
            or unknown commands yields an error result instead of raising.
        """
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return ShellResult(output="bash: syntax error: unmatched quote")
        if not tokens:
            return ShellResult()
        name, args = tokens[0], tokens[1:]
        handler = getattr(self, f"_cmd_{name}", None)
        if handler is None:
            return ShellResult(output=f"bash: {name}: command not found")
        return handler(args)

    def _cmd_help(self, args: list[str]) -> ShellResult:
        """Show the supported command list.

        Args:
            args: Ignored.

        Returns:
            The help text.
        """
        return ShellResult(output=HELP_TEXT)

    def _cmd_ls(self, args: list[str]) -> ShellResult:
        """List directory contents, optionally with hidden files or details.

        Args:
            args: ``-a``/``--all`` and ``-l`` flags plus optional target
                paths, defaulting to the working directory.

        Returns:
            Sorted entry names, or an error result for bad flags or
            missing paths.
        """
        show_all = False
        long_format = False
        targets: list[str] = []
        for arg in args:
            if arg == "--all":
                show_all = True
            elif arg.startswith("--"):
                return ShellResult(output=f"ls: unrecognized option '{arg}'")
            elif arg.startswith("-") and arg != "-":
                for flag in arg[1:]:
                    if flag == "a":
                        show_all = True
                    elif flag == "l":
                        long_format = True
                    else:
                        return ShellResult(output=f"ls: invalid option -- '{flag}'")
            else:
                targets.append(arg)
        if not targets:
            targets = ["."]

        errors: list[str] = []
        file_entries: list[tuple[str, dict | str]] = []
        dir_entries: list[tuple[str, dict]] = []
        for target in targets:
            node = self._node(self._resolve(target))
            if node is None:
                errors.append(f"ls: cannot access '{target}': No such file or directory")
            elif isinstance(node, dict):
                dir_entries.append((target, node))
            else:
                file_entries.append((target, node))

        blocks = ["\n".join(errors)] if errors else []
        if file_entries:
            blocks.append("\n".join(self._render(file_entries, long_format)))
        for target, node in dir_entries:
            body = "\n".join(self._render(self._listing(node, show_all), long_format))
            blocks.append(f"{target}:\n{body}" if len(targets) > 1 else body)
        return ShellResult(output="\n\n".join(blocks))

    def _cmd_cd(self, args: list[str]) -> ShellResult:
        """Change the working directory.

        Args:
            args: Zero or one path; with no path the shell goes home.

        Returns:
            An empty result on success, or an error result when the path
            is missing, ambiguous, or not a directory.
        """
        if len(args) > 1:
            return ShellResult(output="cd: too many arguments")
        raw = args[0] if args else "~"
        path = self._resolve(raw)
        node = self._node(path)
        if node is None:
            return ShellResult(output=f"cd: no such file or directory: {raw}")
        if not isinstance(node, dict):
            return ShellResult(output=f"cd: not a directory: {raw}")
        self.cwd = path
        return ShellResult()

    def _cmd_pwd(self, args: list[str]) -> ShellResult:
        """Print the absolute working directory.

        Args:
            args: Ignored.

        Returns:
            The current working directory.
        """
        return ShellResult(output=self.cwd)

    def _cmd_cat(self, args: list[str]) -> ShellResult:
        """Print file contents and record which files were read.

        Args:
            args: One or more file paths.

        Returns:
            Concatenated file contents plus the absolute paths read, or
            per-file error lines for missing paths and directories.
        """
        if not args:
            return ShellResult(output="cat: missing operand")
        lines: list[str] = []
        read_paths: list[str] = []
        for raw in args:
            path = self._resolve(raw)
            node = self._node(path)
            if node is None:
                lines.append(f"cat: {raw}: No such file or directory")
            elif isinstance(node, dict):
                lines.append(f"cat: {raw}: Is a directory")
            else:
                lines.append(node)
                read_paths.append(path)
        return ShellResult(output="\n".join(lines), read_paths=tuple(read_paths))

    def _cmd_find(self, args: list[str]) -> ShellResult:
        """Search the tree below an optional root path.

        Args:
            args: Optional root path plus ``-name``/``-iname`` patterns
                and ``-type f|d`` filters.

        Returns:
            Sorted matching paths including the root itself, or an error
            result for bad predicates or missing paths.
        """
        root: str | None = None
        name_pattern: str | None = None
        ignore_case = False
        kind: str | None = None
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in ("-name", "-iname", "-type"):
                if index + 1 >= len(args):
                    return ShellResult(output=f"find: missing argument to '{arg}'")
                value = args[index + 1]
                index += 2
                if arg == "-type":
                    if value not in ("f", "d"):
                        return ShellResult(output=f"find: unknown argument to -type: {value}")
                    kind = value
                else:
                    name_pattern = value
                    ignore_case = arg == "-iname"
            elif not arg.startswith("-") and root is None:
                root = arg
                index += 1
            else:
                return ShellResult(output=f"find: unknown predicate '{arg}'")

        raw = root if root is not None else "."
        node = self._node(self._resolve(raw))
        if node is None:
            return ShellResult(output=f"find: '{raw}': No such file or directory")

        matches: list[str] = []
        root_name = posixpath.basename(raw.rstrip("/")) or raw
        for display, name, entry in self._walk(raw, root_name, node):
            if kind == "f" and isinstance(entry, dict):
                continue
            if kind == "d" and not isinstance(entry, dict):
                continue
            if name_pattern is not None:
                subject, pattern = (name.lower(), name_pattern.lower()) if ignore_case else (name, name_pattern)
                if not fnmatch.fnmatchcase(subject, pattern):
                    continue
            matches.append(display)
        return ShellResult(output="\n".join(sorted(matches)))

    def _walk(self, display: str, name: str, node: dict | str) -> list[tuple[str, str, dict | str]]:
        """Collect a node and every descendant depth-first.

        Args:
            display: Display path of the node.
            name: Entry name of the node.
            node: Filesystem node to walk.

        Returns:
            ``(display path, name, node)`` triples starting with the node
            itself.
        """
        found = [(display, name, node)]
        if isinstance(node, dict):
            for child_name, child in node.items():
                found.extend(self._walk(posixpath.join(display, child_name), child_name, child))
        return found

    def _cmd_tree(self, args: list[str]) -> ShellResult:
        """Show a directory as an indented tree.

        Args:
            args: Optional ``-a`` flag to include hidden entries plus at
                most one target path.

        Returns:
            The tree rendering, or an error result for bad options,
            multiple targets, or missing paths.
        """
        show_all = False
        targets: list[str] = []
        for arg in args:
            if arg == "-a":
                show_all = True
            elif arg.startswith("-"):
                return ShellResult(output=f"tree: unrecognized option '{arg}'")
            else:
                targets.append(arg)
        if len(targets) > 1:
            return ShellResult(output="tree: too many arguments")
        raw = targets[0] if targets else "."
        node = self._node(self._resolve(raw))
        if node is None:
            return ShellResult(output=f"tree: {raw}: No such file or directory")
        lines = [raw]
        if isinstance(node, dict):
            lines.extend(self._tree_lines(node, "", show_all))
        return ShellResult(output="\n".join(lines))

    def _tree_lines(self, node: dict, prefix: str, show_all: bool) -> list[str]:
        """Render one directory level of a tree diagram.

        Args:
            node: Directory whose entries are rendered.
            prefix: Indentation inherited from ancestor levels.
            show_all: Whether to include dotfile entries.

        Returns:
            One line per entry, recursing into subdirectories.
        """
        names = sorted(name for name in node if show_all or not name.startswith("."))
        lines: list[str] = []
        for index, name in enumerate(names):
            last = index == len(names) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}")
            child = node[name]
            if isinstance(child, dict):
                lines.extend(self._tree_lines(child, prefix + ("    " if last else "│   "), show_all))
        return lines

    def _cmd_whoami(self, args: list[str]) -> ShellResult:
        """Print the current login name.

        Args:
            args: Ignored.

        Returns:
            The shell user.
        """
        return ShellResult(output=self.user)

    def _cmd_clear(self, args: list[str]) -> ShellResult:
        """Request a screen clear.

        Args:
            args: Ignored.

        Returns:
            A result with ``clear_requested`` set.
        """
        return ShellResult(clear_requested=True)

    def _cmd_exit(self, args: list[str]) -> ShellResult:
        """Request leaving the shell; also serves logout and shutdown.

        Args:
            args: Ignored.

        Returns:
            A result with ``exit_requested`` set.
        """
        return ShellResult(exit_requested=True)

    _cmd_logout = _cmd_exit
    _cmd_shutdown = _cmd_exit

    def _listing(self, node: dict, show_all: bool) -> list[tuple[str, dict | str]]:
        """Sort directory entries, adding ``.`` and ``..`` when requested.

        Args:
            node: Directory whose entries are listed.
            show_all: Whether to include hidden entries and ``.``/``..``.

        Returns:
            Sorted ``(name, node)`` pairs ready for rendering.
        """
        names = sorted(name for name in node if show_all or not name.startswith("."))
        entries = [(name, node[name]) for name in names]
        if show_all:
            entries = [(".", {}), ("..", {})] + entries
        return entries

    def _render(self, entries: list[tuple[str, dict | str]], long_format: bool) -> list[str]:
        """Format entries as plain names or ``ls -l`` style lines.

        Args:
            entries: ``(name, node)`` pairs to format.
            long_format: Whether to use the long listing format.

        Returns:
            One rendered line per entry.
        """
        if not long_format:
            return [name for name, _ in entries]
        lines = []
        for name, node in entries:
            if isinstance(node, dict):
                lines.append(f"drwxr-xr-x 1 teacher users {4096:>5} Jan 01 00:00 {name}")
            else:
                lines.append(f"-rw-r--r-- 1 teacher users {len(node):>5} Jan 01 00:00 {name}")
        return lines

    def _resolve(self, path: str) -> str:
        """Resolve a user path to an absolute, normalized virtual path.

        Args:
            path: Absolute path, ``~``-prefixed path, or path relative to
                the working directory.

        Returns:
            The normalized absolute path.
        """
        if path == "~" or path.startswith("~/"):
            path = self.home + path[1:]
        elif not path.startswith("/"):
            path = posixpath.join(self.cwd, path)
        return "/" + posixpath.normpath(path).lstrip("/")

    def _node(self, path: str) -> dict | str | None:
        """Look up the filesystem node at an absolute path.

        Args:
            path: Absolute virtual path.

        Returns:
            The directory dict, file string, or None when missing.
        """
        node: dict | str = self.filesystem
        for part in path.split("/"):
            if part == "":
                continue
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


SERVER_HELP_TEXT = """Available commands:
  ls [-a] [-l] [path...]   list directory contents
  cd [path]                change directory
  pwd                      print the working directory
  cat <file...>            print file contents
  whoami                   print the current user
  groups                   print the current user's groups
  sudo <command>           run a command with root privileges
  exit                     leave the server or the terminal
  help                     show this help"""


class ServerShell:
    """Shell for the Lab D 2001 server-provisioning challenge.

    The shell plays two machines from one state: the local workstation the
    player starts at, and the server reached over SSH. Commands mutate the
    server state in place, so progress is judged by evaluating state rather
    than by matching command strings.

    Attributes:
        state: The :class:`~src.server_state.ServerState` being played.
    """

    #: Commands that need root privileges.
    _PRIVILEGED = (
        "apt",
        "adduser",
        "usermod",
        "rsync",
        "chown",
        "chmod",
        "cp",
        "mkdir",
        "ln",
        "systemctl",
        "sshd",
        "nginx",
        "ufw",
        "hostnamectl",
        "netplan",
        "timedatectl",
    )

    def __init__(
        self,
        state: ServerState,
        read_line: Callable[[str], str] | None = None,
        write: Callable[[str], None] | None = None,
        editor: Callable[[str], tuple[bool, str]] | None = None,
    ) -> None:
        """Bind a shell to the server state.

        Args:
            state: The challenge state to play.
            read_line: Callable reading one line of input. Defaults to ``input``.
            write: Callable receiving output. Defaults to ``print``.
            editor: Callable opening a file for editing; it receives the file
                text and returns ``(saved, text)``. Defaults to a
                :class:`~src.utils.editor.ModalEditor` session.
        """
        self.state = state
        self._read_line = read_line if read_line is not None else input
        self._write = write if write is not None else print
        self._editor = editor if editor is not None else self._default_editor

    def _default_editor(self, text: str) -> tuple[bool, str]:
        """Open the modal editor on the current terminal."""
        from src.utils.editor import ModalEditor

        return ModalEditor(text, write=self._write).run()

    # -- prompt ------------------------------------------------------------

    @property
    def home(self) -> str:
        """Home directory of the current user."""
        user = self.state.session["user"]
        return "/root" if user == "root" else f"/home/{user}"

    @property
    def prompt(self) -> str:
        """The rendered prompt for the current machine."""
        session = self.state.session
        cwd = session["cwd"]
        home = self.home
        if cwd == home:
            display = "~"
        elif cwd.startswith(home + "/"):
            display = "~" + cwd[len(home) :]
        else:
            display = cwd
        return (
            f"{session['user']}@{session['machine']}:"
            f"{display}{session['prompt_symbol']}"
        )

    # -- execution ---------------------------------------------------------

    def execute(self, command: str) -> ShellResult:
        """Run one command line.

        Args:
            command: Raw input line.

        Returns:
            The command outcome. Malformed input yields an error result
            instead of raising.
        """
        if self.state.session.get("pending_prompt"):
            return self.answer(command)
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return ShellResult(output="bash: syntax error: unmatched quote")
        if not tokens:
            return ShellResult()
        name, args = tokens[0], tokens[1:]
        if name == "sudo":
            return self._run_sudo(args)
        if name in self._PRIVILEGED and self.state.session["user"] != "root":
            return ShellResult(output="Permission denied (are you root?)")
        handler = getattr(self, f"_cmd_{name}", None)
        if handler is None:
            return ShellResult(output=f"bash: {name}: command not found")
        return handler(args)

    def _run_sudo(self, args: list[str]) -> ShellResult:
        """Run a command with elevated rights."""
        user = self.state.session["user"]
        allowed = self.state.system.get("users", {}).get(user, {}).get("sudo")
        if user != "root" and not allowed:
            return ShellResult(
                output=(
                    f"sudo: {user} is not in the sudoers file. "
                    "This incident will be reported."
                )
            )
        if not args:
            return ShellResult(output="sudo: no command given")
        name, rest = args[0], args[1:]
        handler = getattr(self, f"_cmd_{name}", None)
        if handler is None:
            return ShellResult(output=f"bash: {name}: command not found")
        session = self.state.session
        previous = session["user"]
        session["user"] = "root"
        try:
            return handler(rest)
        finally:
            session["user"] = previous

    def answer(self, text: str) -> ShellResult:
        """Resolve the pending sub-prompt with the player's answer.

        Args:
            text: What the player typed.

        Returns:
            The outcome of the interrupted command.
        """
        pending = self.state.session.get("pending_prompt")
        if not pending:
            return ShellResult()
        self.state.session["pending_prompt"] = None
        handler = getattr(self, f"_answer_{pending.get('kind')}", None)
        if handler is None:
            return ShellResult()
        return handler(text, pending)

    def _answer_ssh_host_key(self, text: str, pending: dict) -> ShellResult:
        """Resolve the SSH host-key confirmation prompt."""
        host = pending.get("host", SERVER_IP)
        answer = text.strip().lower()
        if answer == "yes":
            known_hosts = self.state.system.setdefault("known_hosts", [])
            if host not in known_hosts:
                known_hosts.append(host)
            return self._connect(pending.get("user", "root"), pending.get("key"))
        if answer == "no":
            return ShellResult(output=f"Connection to {host} closed.")
        return ShellResult(prompt="Please type 'yes', 'no' or the fingerprint: ")

    # -- filesystem helpers -------------------------------------------------

    def _resolve(self, path: str) -> str:
        """Resolve a path to an absolute, normalized virtual path."""
        if path == "~" or path.startswith("~/"):
            path = self.home + path[1:]
        elif not path.startswith("/"):
            path = posixpath.join(self.state.session["cwd"], path)
        return "/" + posixpath.normpath(path).lstrip("/")

    def _node(self, path: str) -> dict | None:
        """Return the filesystem node at an absolute path."""
        return self.state.filesystem.get(path)

    def _children(self, path: str) -> list[str]:
        """Names of the entries directly inside a directory."""
        prefix = path if path.endswith("/") else path + "/"
        names = []
        for candidate in self.state.filesystem:
            if candidate.startswith(prefix):
                rest = candidate[len(prefix) :]
                if rest and "/" not in rest:
                    names.append(rest)
        return sorted(names)

    def _is_dir(self, path: str) -> bool:
        """True when a path is a directory."""
        node = self._node(path)
        if node is not None and node.get("type") == "dir":
            return True
        return bool(self._children(path))

    # -- commands -----------------------------------------------------------

    def _cmd_pwd(self, args: list[str]) -> ShellResult:
        """Print the working directory."""
        return ShellResult(output=self.state.session["cwd"])

    def _cmd_cd(self, args: list[str]) -> ShellResult:
        """Change the working directory."""
        if len(args) > 1:
            return ShellResult(output="cd: too many arguments")
        raw = args[0] if args else "~"
        path = self._resolve(raw)
        if self._node(path) is None and not self._is_dir(path):
            return ShellResult(output=f"cd: no such file or directory: {raw}")
        if not self._is_dir(path):
            return ShellResult(output=f"cd: not a directory: {raw}")
        self.state.session["cwd"] = path
        return ShellResult()

    def _cmd_ls(self, args: list[str]) -> ShellResult:
        """List directory contents."""
        show_all = False
        long_format = False
        targets: list[str] = []
        for arg in args:
            if arg == "--all":
                show_all = True
            elif arg.startswith("--"):
                return ShellResult(output=f"ls: unrecognized option '{arg}'")
            elif arg.startswith("-") and arg != "-":
                for flag in arg[1:]:
                    if flag == "a":
                        show_all = True
                    elif flag == "l":
                        long_format = True
                    else:
                        return ShellResult(output=f"ls: invalid option -- '{flag}'")
            else:
                targets.append(arg)
        if not targets:
            targets = ["."]

        errors: list[str] = []
        blocks: list[str] = []
        for target in targets:
            path = self._resolve(target)
            if self._node(path) is None and not self._is_dir(path):
                errors.append(
                    f"ls: cannot access '{target}': No such file or directory"
                )
                continue
            if not self._is_dir(path):
                blocks.append(path)
                continue
            names = self._children(path)
            if not show_all:
                names = [name for name in names if not name.startswith(".")]
            if long_format:
                lines = [self._long_entry(path, name) for name in names]
            else:
                lines = names
            body = "\n".join(lines)
            blocks.append(f"{target}:\n{body}" if len(targets) > 1 else body)
        return ShellResult(output="\n\n".join([*errors, *blocks]))

    def _long_entry(self, directory: str, name: str) -> str:
        """Render one ``ls -l`` line."""
        path = posixpath.join(directory, name)
        node = self._node(path)
        if node is None or node.get("type") == "dir":
            mode = "drwxr-xr-x"
            size = 4096
            owner = node.get("owner", "root:root") if node else "root:root"
        else:
            mode = "-rw-r--r--"
            size = len(node.get("content", ""))
            owner = node.get("owner", "root:root")
        return f"{mode} 1 {owner} {size:>6} Jan 01 00:00 {name}"

    def _cmd_cat(self, args: list[str]) -> ShellResult:
        """Print file contents."""
        if not args:
            return ShellResult(output="cat: missing operand")
        lines: list[str] = []
        read_paths: list[str] = []
        for raw in args:
            path = self._resolve(raw)
            node = self._node(path)
            if node is None:
                lines.append(f"cat: {raw}: No such file or directory")
            elif node.get("type") == "dir":
                lines.append(f"cat: {raw}: Is a directory")
            else:
                lines.append(node.get("content", ""))
                read_paths.append(path)
        return ShellResult(output="\n".join(lines), read_paths=tuple(read_paths))

    def _cmd_whoami(self, args: list[str]) -> ShellResult:
        """Print the current user."""
        return ShellResult(output=self.state.session["user"])

    def _cmd_groups(self, args: list[str]) -> ShellResult:
        """Print the groups of the current user."""
        user = self.state.session["user"]
        if user == "root":
            return ShellResult(output="root sudo")
        if self.state.system.get("users", {}).get(user, {}).get("sudo"):
            return ShellResult(output=f"{user} sudo")
        return ShellResult(output=user)

    def _cmd_help(self, args: list[str]) -> ShellResult:
        """Show the supported commands."""
        return ShellResult(output=SERVER_HELP_TEXT)

    def _cmd_clear(self, args: list[str]) -> ShellResult:
        """Request a screen clear."""
        return ShellResult(clear_requested=True)

    def _cmd_exit(self, args: list[str]) -> ShellResult:
        """Leave the server, or the terminal when already on the workstation."""
        session = self.state.session
        if session["machine"] == LOCAL_MACHINE:
            return ShellResult(exit_requested=True)
        session["machine"] = LOCAL_MACHINE
        session["user"] = LOCAL_USER
        session["cwd"] = f"/home/{LOCAL_USER}"
        session["prompt_symbol"] = "$"
        session["connected_via_ssh"] = False
        return ShellResult(output="Connection to maze-server closed.")

    # -- remote access -----------------------------------------------------

    def _cmd_ssh(self, args: list[str]) -> ShellResult:
        """Connect to the server over SSH."""
        key = None
        port = None
        target = None
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "-i" and index + 1 < len(args):
                key = args[index + 1]
                index += 2
                continue
            if arg == "-p" and index + 1 < len(args):
                port = args[index + 1]
                index += 2
                continue
            if arg.startswith("-"):
                return ShellResult(output=f"ssh: invalid option -- '{arg[1]}'")
            target = arg
            index += 1
        if target is None or "@" not in target:
            return ShellResult(output="ssh: no hostname given")
        user, host = target.split("@", 1)
        if host != SERVER_IP:
            return ShellResult(
                output=(
                    f"ssh: connect to host {host} port {port or 22}: "
                    "Connection timed out"
                )
            )
        key_path = self._resolve(key) if key else ""
        if not key or self._node(key_path) is None:
            return ShellResult(output=f"{user}@{host}: Permission denied (publickey).")
        if not self._ssh_allows(user):
            return ShellResult(output=f"{user}@{host}: Permission denied (publickey).")
        if host not in self.state.system.get("known_hosts", []):
            self.state.session["pending_prompt"] = {
                "kind": "ssh_host_key",
                "host": host,
                "user": user,
                "key": key_path,
            }
            return ShellResult(
                prompt=(
                    f"The authenticity of host '{host} ({host})' can't be established.\n"
                    "ED25519 key fingerprint is "
                    "SHA256:x7k9LmP2qR8vN1wZ4yB6cF0jH3dG5sA8tE9uI2oP4lM.\n"
                    "Are you sure you want to continue connecting "
                    "(yes/no/[fingerprint])? "
                )
            )
        return self._connect(user, key_path)

    def _ssh_allows(self, user: str) -> bool:
        """True when the sshd configuration still lets this user in."""
        parsed = self.state.filesystem.get("/etc/ssh/sshd_config", {}).get("parsed", {})
        entry = self.state.system.get("users", {}).get(user)
        if entry is None:
            return False
        if user == "root" and parsed.get("PermitRootLogin") == "no":
            return False
        return bool(entry.get("has_ssh_key"))

    def _connect(self, user: str, key_path: str | None = None) -> ShellResult:
        """Switch the session onto the server as ``user``.

        The key used to connect is authorised on the server, so it can be copied
        to another account later.
        """
        session = self.state.session
        session["connected_via_ssh"] = True
        session["machine"] = SERVER_HOSTNAME
        session["user"] = user
        session["cwd"] = "/root" if user == "root" else f"/home/{user}"
        session["prompt_symbol"] = "#" if user == "root" else "$"
        if key_path:
            key_node = self._node(key_path)
            authorized = self._node("/root/.ssh/authorized_keys")
            if key_node is not None and authorized is not None:
                content = authorized.get("content", "")
                if key_node.get("content", "") not in content:
                    authorized["content"] = content + key_node.get("content", "")
        return ShellResult()

    def _cmd_su(self, args: list[str]) -> ShellResult:
        """Switch to another user."""
        name = None
        for arg in args:
            if arg == "-":
                continue
            name = arg
        if name is None:
            name = "root"
        if name not in self.state.system.get("users", {}):
            return ShellResult(output=f"su: user '{name}' does not exist")
        session = self.state.session
        session["user"] = name
        session["cwd"] = "/root" if name == "root" else f"/home/{name}"
        session["prompt_symbol"] = "#" if name == "root" else "$"
        return ShellResult()

    # -- packages and users ------------------------------------------------

    def _cmd_apt(self, args: list[str]) -> ShellResult:
        """Update or install system packages."""
        if not args:
            return ShellResult(output="apt: no operation specified")
        operation, rest = args[0], args[1:]
        system = self.state.system
        if operation in ("update", "refresh"):
            system["pkg_index_updated"] = True
            return ShellResult(
                output=(
                    "Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease\n"
                    "Get:2 http://archive.ubuntu.com/ubuntu jammy-updates InRelease"
                )
            )
        if operation == "upgrade":
            if not system.get("pkg_index_updated"):
                return ShellResult(output="0 upgraded, 0 newly installed, 0 to remove")
            if "-y" in rest or "--yes" in rest:
                system["pkg_upgraded"] = True
                return ShellResult(
                    output=(
                        "Calculating upgrade... Done\n"
                        "0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded."
                    )
                )
            self.state.session["pending_prompt"] = {"kind": "apt_confirm"}
            return ShellResult(prompt="Do you want to continue? [Y/n] ")
        if operation == "install":
            packages = [arg for arg in rest if not arg.startswith("-")]
            if not packages:
                return ShellResult(output="apt: no packages specified")
            for package in packages:
                if package != "nginx":
                    return ShellResult(output=f"E: Unable to locate package {package}")
            system["services"]["nginx"]["installed"] = True
            return ShellResult(
                output=(
                    "Setting up nginx (1.18.0-6ubuntu14.3) ...\n"
                    "Processing triggers for man-db (2.10.2-1) ..."
                )
            )
        return ShellResult(output=f"apt: invalid operation '{operation}'")

    _cmd_apt_get = _cmd_apt

    def _answer_apt_confirm(self, text: str, pending: dict) -> ShellResult:
        """Resolve the package-upgrade confirmation prompt."""
        if text.strip().lower() in ("", "y", "yes"):
            self.state.system["pkg_upgraded"] = True
            return ShellResult(
                output=(
                    "Calculating upgrade... Done\n"
                    "0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded."
                )
            )
        return ShellResult(output="Abort.")

    def _cmd_adduser(self, args: list[str]) -> ShellResult:
        """Create a user account."""
        if not args:
            return ShellResult(output="adduser: no username specified")
        if len(args) > 1:
            return ShellResult(output="adduser: Only one or two names allowed.")
        name = args[0]
        users = self.state.system.setdefault("users", {})
        if name in users:
            return ShellResult(output=f"adduser: user '{name}' already exists")
        users[name] = {"sudo": False, "has_ssh_key": False}
        if self.state.system.get("admin_user") is None:
            self.state.system["admin_user"] = name
        home = f"/home/{name}"
        self.state.filesystem.setdefault(
            home, {"type": "dir", "perms": "755", "owner": f"{name}:{name}"}
        )
        self.state.filesystem.setdefault(
            f"{home}/.ssh", {"type": "dir", "perms": "700", "owner": f"{name}:{name}"}
        )
        self.state.session["pending_prompt"] = {
            "kind": "adduser_password",
            "user": name,
            "stage": "password",
        }
        return ShellResult(prompt="New password: ")

    def _answer_adduser_password(self, text: str, pending: dict) -> ShellResult:
        """Resolve the adduser password and confirmation prompts."""
        stage = pending.get("stage", "password")
        name = pending.get("user", "")
        if stage == "password":
            if not text:
                return ShellResult(prompt="New password: ")
            pending["password"] = text
            pending["stage"] = "retype"
            return ShellResult(prompt="Retype new password: ")
        if stage == "retype":
            if text != pending.get("password"):
                pending["stage"] = "password"
                return ShellResult(prompt="New password: ")
            pending["stage"] = "confirm"
            return ShellResult(prompt="Is the information correct? [Y/n] ")
        if text.strip().lower() in ("", "y", "yes"):
            return ShellResult(output=f"useradd: user '{name}' created with home directory")
        self.state.system.get("users", {}).pop(name, None)
        if self.state.system.get("admin_user") == name:
            self.state.system["admin_user"] = None
        return ShellResult(output="adduser: cancelled")

    def _cmd_usermod(self, args: list[str]) -> ShellResult:
        """Change a user's group memberships."""
        users = self.state.system.get("users", {})
        append = False
        group = None
        name = None
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "-a":
                append = True
            elif arg == "-aG":
                append = True
                if index + 1 < len(args):
                    group = args[index + 1]
                    index += 1
            elif arg == "-G":
                if index + 1 < len(args):
                    group = args[index + 1]
                    index += 1
            elif arg.startswith("-"):
                return ShellResult(output=f"usermod: invalid option -- '{arg[1]}'")
            else:
                name = arg
            index += 1
        if name is None:
            return ShellResult(output="usermod: no user specified")
        if name not in users:
            return ShellResult(output=f"usermod: user '{name}' does not exist")
        if group != "sudo":
            return ShellResult(output="usermod: only the sudo group is supported")
        if not append:
            return ShellResult(
                output=(
                    "usermod: warning 'G' group memberships overwritten; "
                    "use -a to append"
                )
            )
        users[name]["sudo"] = True
        return ShellResult()

    def _cmd_rsync(self, args: list[str]) -> ShellResult:
        """Copy a home directory's .ssh folder to another account."""
        owner = None
        paths: list[str] = []
        for arg in args:
            if arg.startswith("--chown="):
                owner = arg.split("=", 1)[1]
            elif arg.startswith("-"):
                continue
            else:
                paths.append(arg)
        if len(paths) < 2:
            return ShellResult(output="rsync: missing destination")
        source, destination = paths[0], paths[1]
        source_path = self._resolve(source)
        if not source_path.endswith("/.ssh") or not self._is_dir(source_path):
            return ShellResult(output="rsync: unsupported source path")
        target = owner.split(":")[0] if owner else destination.rstrip("/").rsplit("/", 1)[-1]
        users = self.state.system.get("users", {})
        if target not in users:
            return ShellResult(output=f"rsync: chown: user '{target}' does not exist")
        destination_ssh = posixpath.join(self._resolve(destination), ".ssh")
        self.state.filesystem.setdefault(
            destination_ssh,
            {"type": "dir", "perms": "700", "owner": f"{target}:{target}"},
        )
        copied = 0
        for name in self._children(source_path):
            node = self._node(posixpath.join(source_path, name))
            if node is None:
                continue
            new_node = dict(node)
            new_node["owner"] = owner or f"{target}:{target}"
            self.state.filesystem[posixpath.join(destination_ssh, name)] = new_node
            copied += 1
        users[target]["has_ssh_key"] = True
        return ShellResult(output=f"sent {copied} bytes  received 12 bytes  total 15 bytes")

    # -- services ----------------------------------------------------------

    def _cmd_systemctl(self, args: list[str]) -> ShellResult:
        """Enable, start, restart, reload or query a systemd service."""
        start_now = "--now" in args
        words = [arg for arg in args if arg != "--now"]
        if not words:
            return ShellResult(output="systemctl: no operation specified")
        action = words[0]
        if len(words) < 2:
            return ShellResult(output="systemctl: no unit specified")
        unit = words[1]
        services = self.state.system.get("services", {})
        service = services.get(unit)
        if service is None:
            return ShellResult(
                output=f"Failed to {action} {unit}: Unit {unit}.service not found."
            )
        if unit == "sshd":
            parsed = self.state.filesystem.get("/etc/ssh/sshd_config", {}).get("parsed", {})
            if action in ("reload", "restart") and not parsed.get("syntax_valid"):
                return ShellResult(
                    output=(
                        "Job for ssh.service failed because the control process "
                        "exited with error code."
                    )
                )
            if action == "enable":
                service["enabled"] = True
                if start_now:
                    service["running"] = True
            elif action in ("start", "restart", "reload"):
                service["running"] = True
                service["port"] = parsed.get("Port", service.get("port", 22))
            elif action == "status":
                return self._service_status(unit, service)
            return ShellResult()
        if unit == "nginx":
            site = self.state.filesystem.get("/etc/nginx/sites-available/app", {}).get(
                "parsed", {}
            )
            if action in ("reload", "restart", "start") and not site.get(
                "syntax_valid", True
            ):
                return ShellResult(
                    output=(
                        "Job for nginx.service failed because the control process "
                        "exited with error code."
                    )
                )
            if action == "enable":
                service["enabled"] = True
                if start_now:
                    service["running"] = True
            elif action in ("start", "restart", "reload"):
                service["running"] = True
            elif action == "status":
                return self._service_status(unit, service)
            return ShellResult()
        return ShellResult(output=f"Failed to {action} {unit}: Unit {unit}.service not found.")

    def _service_status(self, unit: str, service: dict) -> ShellResult:
        """Report a service's status and record the health check."""
        if service.get("running"):
            self.state.system["health_verified"]["service_status_checked"] = True
            return ShellResult(
                output=(
                    f"● {unit}.service - {unit} service\n"
                    "     Loaded: loaded (/lib/systemd/system/"
                    f"{unit}.service; enabled)\n"
                    "     Active: active (running)"
                )
            )
        return ShellResult(
            output=(
                f"● {unit}.service - {unit} service\n"
                "     Loaded: loaded (/lib/systemd/system/"
                f"{unit}.service; disabled)\n"
                "     Active: inactive (dead)"
            )
        )

    def _cmd_sshd(self, args: list[str]) -> ShellResult:
        """Validate the sshd configuration."""
        if "-t" not in args:
            return ShellResult(output="usage: sshd -t")
        parsed = self.state.filesystem.get("/etc/ssh/sshd_config", {}).get("parsed", {})
        if parsed.get("syntax_valid"):
            return ShellResult()
        return ShellResult(
            output="sshd: /etc/ssh/sshd_config: line 3: Bad configuration option"
        )
