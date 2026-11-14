# Server Configuration Challenge — Design Document

Date: 2026-11-14
Status: Ready for partner approval (builder check done, gaps resolved)

> **Placement note.** The brainstorming skill wants this committed to
> `docs/superpowers/specs/2026-11-14-server-configuration-challenge-design.md`.
> It was written here first because the session is in Plan mode (writes are
> restricted to this directory). Move it into the repo at the paths named above
> as the first implementation step.

## 1. Intent

The A-maze-ing-Delft game already has one terminal challenge: the NixOS shell in
Teacher Room 4 where the player explores a filesystem to find a secret key. It is a
short scavenger hunt with no stakes.

This project adds a second, much larger terminal challenge in Lab D 2001: a full
sysadmin provisioning run. The player sits at a lab workstation, SSHes into the
server that hosts the A-maze-ing-Delft robot backend, and must harden, network,
and service that box over 11 steps before the robot's neural link can come up.

**Why it exists in the game:** the robot's CHAT phase depends on a working backend.
Provisioning the server is the new gate in front of activation, so the sysadmin
work is narrative, not a side quest.

**Why it is a good fit for the player:** it is the one activity in the game that
rewards planning rather than exploration. Every step has a plausible wrong order,
and several mistakes look like success until you disconnect.

## 2. Goals, non-goals, anti-goals

### Goals

- An 11-step provisioning challenge playable entirely through a terminal in Lab D 2001.
- The player works across **two machines**: a local workstation shell, and the remote
  server reached over SSH.
- A shell that mutates a state model, so progress is determined by evaluating state,
  not by matching a single expected command string.
- A nano-style **character-level** modal editor for editing config files.
- Server progress **persists** in the game state, so leaving the room and coming
  back (or saving and reloading) resumes the challenge exactly where it was.
- Completing the challenge **awards an item** and **sets a flag**.
- The award is **gated**: the robot cannot be activated until the server is provisioned.

### Non-goals

- No real networking, no real filesystem access, no subprocess execution.
- No rollback/checkpoint system (the source spec mentions "checkpoint rollback"
  for the firewall lockout trap; we cut that and instead roll the firewall
  configuration back to its pre-`enable` state — see §4.3 and §4.8).
- No support for editing arbitrary files outside the configured set.
- No multi-window or background job control (`&`, pipes, redirects).
- No terminal emulation beyond what the existing `VirtualShell` already does.

### Anti-goals

- **Not a scripted quiz.** The player must be able to solve steps in a different
  order than the spec lists, and the shell must accept reasonable variations
  (`apt-get` for `apt`, `systemctl restart` for `reload`, `mkdir -p` for `mkdir`).
  A hardcoded "if the command string equals X, advance the counter" implementation
  fails the anti-goal.
- **Not a maze of exact strings.** The player should not need the spec open to
  pass. Error messages should teach the fix ("sshd port 2222 is not allowed by
  the firewall; run: ufw allow 2222/tcp").
- **Not a regression to the existing shell.** Teacher Room 4's `VirtualShell` must
  keep working exactly as it does now.

## 3. Constraints

- **Existing code must keep working.** `src/utils/shell.py` currently backs the
  Teacher Room 4 NixOS challenge and has its own test file (`tests/test_shell.py`).
  `src/rooms/teachers_room_4.py` drives it through `run_shell()`.
- **The game's state is the single source of truth** (`docs/STATE_SCHEMA.md`).
  Server progress is a new key in that state, not a side-channel file.
- **State must be strict JSON** — primitives, lists, dicts only. No live objects
  in the persisted state.
- **Python 3.12+, strict-ish typing.** `mypy .` must pass; `ruff check .` must pass.
- **Existing tests must stay green.** The suite is at 219 passing with an 80%
  coverage floor.
- **No new third-party dependencies.** Everything is stdlib: `shlex`, `termios`/`tty`
  on POSIX and `msvcrt` on Windows (the raw-key reading already exists in
  `src/room.py::_read_page_key`).
- **Terminal I/O must be injectable.** The shell and the editor must accept
  key-readers and writers so they are testable without a TTY. The guide pager
  already does this via `monkeypatch.setattr(room, "_read_page_key", ...)`.

## 4. Design

### 4.1 Where the challenge state lives

The user's instruction: *"First extend current game state before create a new one.
You can create a specialized state for the server shell if necessary."*

**Decision:** extend the game state with a new top-level key `server`, and let
`State` expose it as a typed view.

```
state["server"] = {
  "session":  { machine, user, home, cwd, prompt_symbol, connected_via_ssh,
                pending_prompt },
  "filesystem": { "<absolute path>": <node>, ... },
  "system":   { ip_address, known_hosts, pkg_index_updated, pkg_upgraded,
                users, hostname, timezone, ntp_synced, firewall, services,
                health_verified }
}
```

This is the spec's schema, re-themed. It lives inside the game's `data` dict, so
it is persisted by `State.__snapshot()` like everything else — which satisfies
"server progress should be remembered".

`State` gains:

- `_PERSIST_KEYS` gains `"server"`, so `persist()` writes it to `data/user.json`.
- `State.server` — a property returning a `ServerState` view over
  `self.data["server"]`, defaulting to `ServerState.default()` when absent (so an
  old save without the key still loads).

**Why not a separate `ServerState` object stored in the game state?** Because
`docs/STATE_SCHEMA.md` forbids live objects in the persisted state. The
`ServerState` class is a *view/validator* over plain dicts, not a stored object.
It is created on demand from `state["server"]` and mutates the underlying dict in
place, so persistence keeps working unchanged.

**One filesystem tree, two machines.** The spec uses a single `filesystem` map and
it works because the two machines' paths never collide: the local workstation
lives under `/home/player`, the server under `/root` and `/etc`. The `~`
expansion follows the *current* user and home, so the same tree serves both.
This avoids duplicating a large tree per machine.

**Node schema** (see §4.5):

```
"<path>": { "type": "file", "content": "<text>", "perms": "600",
             "owner": "root:root", "parsed": { ...structured fields... } }
"<path>": { "type": "dir", "entries": { ...children... },
             "perms": "755", "owner": "root:root" }
```

`content` is the editable text; `parsed` holds the structured fields the spec
wants (`PermitRootLogin`, `syntax_valid`, `static_ip_set`, …) and is re-derived
from `content` by that file's parser on save. One source of truth per file:
the text, with `parsed` as its derived view.

**Backfill for existing saves.** `State.__load_static` only fills `items` from
`default.json` when the key is *absent* from `user.json`, and `flags` is copied
verbatim. A player with an existing save would therefore miss the new item
definition and the new flag, and `self.items[item_id]` / `self.flags[...]` index
directly — a `KeyError` at award time. The build must add a backfill in
`State.normalize_state` (alongside the existing `__backfill_terminal_state`) that
adds any `default.json` item missing from the save, and any default flag missing
from the save's `flags` dict. The promise "an old save without the key still
loads" covers items and flags, not just `server`.


### 4.2 Module layout

| File | Responsibility |
|------|----------------|
| `src/server_state.py` | **New.** `ServerState` — the typed view over `state["server"]`: defaults, step evaluation, config-file parsing, mutation helpers. Pure logic, no I/O. |
| `src/utils/shell.py` | **Extended.** `VirtualShell` keeps its current behavior for Teacher Room 4. A new `ServerShell` subclass adds the server commands, `sudo`, sub-prompts, and machine switching. |
| `src/utils/editor.py` | **New.** `ModalEditor` — the nano-style character-level editor, with injected key reader/writer. |
| `src/rooms/lab_d2_001.py` | **Extended.** `inspect_server()` boots the local workstation shell; on SSH it hands over to the server shell. |
| `src/rooms/lab_d2_002.py` | **Extended.** `activate()` refuses until the server is provisioned. |
| `src/state.py` | **Extended.** `server` property + `_PERSIST_KEYS`. |
| `data/default.json` | **Extended.** `server` template, `lab_server_provisioned` flag, the awarded item. |

### 4.3 The two machines

The player starts at the **local workstation** (`player@thuas-workstation:~$`),
exactly as `lab_d2_001.py::inspect_server` already prompts today.

```
local-workstation  --ssh [-p port] [-i key] user@10.11.7.42-->  maze-server
```

- The local shell has a tiny command set: `ls`, `cat`, `cd`, `pwd`, `ssh`, `help`.
  `cat ~/.ssh/id_ed25519` reveals the key file. `ssh` is the only way forward.
- The server shell has the full command set.
- `session.machine` distinguishes them; the prompt renders from it.
- `exit` on the server returns to the local workstation (not out of the game);
  `exit` on the local workstation ends the terminal session and returns to the room.

**SSH accepts any user, and authentication is per-user.** `ssh [options] user@host`
authenticates the named user against that user's `authorized_keys`, and honours
`PermitRootLogin` and `PasswordAuthentication`. This is what makes several
elements of the spec live rather than decorative:

- `sudo` has real meaning: it requires `system.users[user].sudo == true`, and
  commands touching `/etc`, packages, firewall, or services refuse otherwise
  (`Permission denied (are you root?)`). A player who stays `root` for the whole
  run never sees it; one who drops to `maze-admin` with `su - maze-admin` does.
- Step 3's `sudo` group membership and copied SSH key are the difference between
  being locked out and not.
- The SSH-lockout trap is reachable: it fires on the *next* connection attempt.

**Reconnecting after a lockout** is possible as `maze-admin@10.11.7.42` with the
copied key. The player is not required to disconnect mid-run; the trap only bites
if they do.

**The SSH port is changeable end to end.** `Port` in `sshd_config` moves the
service, `ufw allow <port>/tcp` must match it, `ss -tulpn` reports the new port,
and the local shell's `ssh -p <port>` reaches it. Port 22 is the default and
staying on 22 is a valid solution; the port is only *optional*.

**Recovery from the firewall lockout.** The spec's "checkpoint rollback" is cut,
so severing the session without a recovery path would soft-lock the game (the
local shell cannot run `ufw allow` on the server). Instead:

> When `ufw enable` severs the session because the SSH port is not allowed, the
> firewall configuration is **rolled back to its pre-`enable` state** (the rules
> the player entered are kept, `active` reverts to `false`, and default policies
> revert to `allow`/`allow`), the player is returned to the local workstation,
> and the message explains why.

This keeps the trap's teeth — the player loses the session and must redo the
firewall step correctly — while guaranteeing the challenge stays winnable, with
or without saving. The rules the player already entered survive the rollback, so
the retry is quick.


### 4.4 Re-theming (decided with the user)

| Source spec | This game |
|---|---|
| `203.0.113.42` | `10.11.7.42` — campus-private address |
| `ubuntu-server` | `maze-server` |
| `prod-server-01.example.com` | `maze-server.thuas.nl` |
| admin user (`adduser <user>`) | `maze-admin` |
| nginx root `/var/www/app` | `/var/www/maze` — the robot's telemetry dashboard |
| `root` | `root` (unchanged) |

The static-IP step must configure `10.11.7.42/24` — the same address the player
SSH'd to in step 1 — otherwise the server would change its own address mid-challenge.

The server is the **A-maze-ing-Delft robot's backend**. This is why provisioning
gates activation, and it is what the awarded item represents.

### 4.5 Shell extension

`ServerShell` extends `VirtualShell` so the existing Teacher Room 4 behavior and
its tests are untouched.

**Filesystem model.** The current `VirtualShell` stores a nested dict where a
string is file content. The server needs files with metadata and mutable content,
so `ServerShell` uses a richer node (§4.1): a file node carries `content`,
`perms`, `owner`, and `parsed`; a directory node carries `entries`, `perms`,
`owner`.

**Config files are text; state is parsed from them.** Each editable file has a
parser that reads its `content` and returns the structured fields the spec wants
(`PermitRootLogin`, `syntax_valid`, `static_ip_set`, …) in `parsed`. This is what
makes "invalid YAML indentation" a real failure: the parser detects it and sets
`syntax_valid = false`. Parsers are **deliberately narrow** — they check the
specific structure the game needs (the keys it cares about, and indentation of
those keys), not real YAML.

**The admin account is the player's choice, not a fixed name.** `adduser <name>`
accepts any name; `maze-admin` is the suggested example, not a requirement.
State tracks the admin as *the first non-root user created* — a `system.admin_user`
field set when `adduser` succeeds — and step 9's predicate becomes
`owner == "<admin_user>:www-data"` or `owner == "www-data:www-data"`. This keeps
the "not a rigid quiz" anti-goal intact and avoids inventing a field the spec
does not have.

**Command set** (beyond the current `ls/cd/pwd/cat/find/tree/clear/whoami/exit/help`):

| Group | Commands |
|---|---|
| Privileges | `sudo` (prefix), `su - <user>`, `groups`, `whoami` |
| Packages | `apt`, `apt-get` (`update`, `upgrade`, `install <pkg>`) |
| Users | `adduser`, `usermod` (`-aG sudo`, `-a -G`), `rsync`, `cp`, `mkdir`, `chown`, `chmod`, `ln -s` |
| Config | `nano`, `vim` (aliases), `sed -i` |
| Services | `systemctl` (`enable`, `start`, `restart`, `reload`, `status`), `service` |
| Validation | `sshd -t`, `nginx -t` |
| Network | `ufw`, `hostnamectl`, `netplan`, `timedatectl`, `ss`, `netstat` |
| Diagnostics | `curl`, `tail`, `journalctl` |
| Remote | `ssh` (local shell only) |
| Progress | `checklist` (see §4.10) |

**Sub-prompts.** The spec needs commands that temporarily take over input
(`ssh` host-key check, `adduser` password, `apt upgrade` `[Y/n]`,
`ufw enable` `(y|n)`). `ServerShell` holds a `pending_prompt` describing the
active question; `execute()` returns a `ShellResult` that asks the caller for a
line, and the next `execute()` call resolves it. This mirrors the spec's
`session.pending_prompt` field.

**Privilege.** `sudo` is a prefix, not a state change: `sudo <cmd>` runs `<cmd>`
with elevated rights. Commands that touch `/etc`, packages, firewall, or services
require elevation when `session.user != "root"`. Without it: `Permission denied (are you root?)`.

**Failures stay informative.** Every error message in the spec is used verbatim
where given, and the "trap" messages double as coaching (see §4.8).


### 4.6 The editor

`src/utils/editor.py::ModalEditor` — a **character-level** modal editor, per the
user's explicit choice over a directive-level one.

- Full-screen redraw of the file with the cursor placed via ANSI escapes.
- Arrow keys move the cursor within and across lines; Home/End; Backspace
  deletes; printable characters insert; Enter inserts a newline.
- `Ctrl+S` saves; `Ctrl+X` exits (prompting to save if dirty).
- Key reading reuses the platform split already proven in
  `src/room.py::_read_page_key` (Windows `msvcrt`, POSIX `termios`/`tty`),
  extracted into a shared helper so both the editor and the guide pager use one
  implementation. Arrow keys arrive as escape sequences on POSIX and as
  two-byte codes on Windows — the helper normalizes both to a single token.
- The editor is **injected** with a key reader and a writer, so tests drive it
  with a scripted key list and assert on the resulting text.

The editor writes the file's text back into the server filesystem; the file's
parser then re-derives its structured fields and `syntax_valid`.

### 4.7 The 11 steps

Step completion is **evaluated from state**, never from a command counter.
Each step is a predicate over `ServerState`:

| # | Step | Complete when |
|---|---|---|
| 1 | SSH connect | `connected_via_ssh` and `known_hosts` contains the IP |
| 2 | Packages | `pkg_index_updated` and `pkg_upgraded` |
| 3 | Admin user | a non-root user exists with `sudo` and `has_ssh_key` |
| 4 | SSH hardening | `PermitRootLogin == "no"`, `PasswordAuthentication == "no"`, `sshd.syntax_valid`, service reloaded |
| 5 | Firewall | `firewall.active`, `default_incoming == "deny"`, ssh port allowed, 80 and 443 allowed |
| 6 | Host & network | `hostname` set, `hosts.mapped_fqdn`, `netplan.static_ip_set` |
| 7 | Time sync | `ntp_synced` |
| 8 | Nginx | `nginx.installed`, site `configured` and `enabled`, `syntax_valid` |
| 9 | Permissions | `/var/www/maze` exists, owner `<admin>:www-data`, perms `755` or `750` |
| 10 | Daemons | `nginx.enabled` and `nginx.running` |
| 11 | Verification | all three `health_verified` flags true |

The win condition is **all 11 steps complete**.

### 4.8 Traps

The spec's traps are the best part of it, so they are all implemented:

- **Firewall lockout** — `ufw enable` while the SSH port is not allowed: the
  session is severed (`client_loop: send disconnect: Broken pipe`) and the
  firewall configuration is **rolled back** to its pre-`enable` state (§4.3). The
  player returns to the local workstation, where SSH now fails, and must redo the
  firewall step correctly.
- **SSH lockout** — reloading `sshd` with root login and password auth disabled
  while no non-root user has an SSH key: subsequent SSH attempts fail. The
  spec's "checkpoint rollback" is cut — instead the player must have provisioned
  a usable admin user first, which is what step 3 is for.
- **Wrong `yes`** — typing `y` at the host-key prompt re-prompts
  (`Please type 'yes', 'no' or the fingerprint: `).
- **Upgrade before update** — `apt upgrade` before `apt update` prints
  `0 upgraded, 0 newly installed, 0 to remove` and does not satisfy the step.
- **Syntax errors** — broken netplan YAML or nginx block sets `syntax_valid = false`,
  and the validating command fails with the spec's message.

### 4.9 The initial server image

The steps' predicates depend on what exists before the player touches anything.
The starting image is fixed:

| Path | Initial state |
|---|---|
| `/etc/ssh/sshd_config` | exists, `PermitRootLogin yes`, `PasswordAuthentication yes`, `Port 22` |
| `/etc/hosts` | exists, does not map the FQDN |
| `/etc/netplan/50-cloud-init.yaml` | exists, no static IP, valid |
| `/etc/nginx/sites-available/app` | **does not exist** — created by the player in step 8 |
| `/etc/nginx/sites-enabled/` | exists (empty) — so `ln -s` works without a `mkdir` |
| `/var/www/maze` | does not exist — created in step 9 |
| `/home/player/.ssh/id_ed25519` | exists on the **local** machine only |

`nano`/`vim` on a path that does not exist **errors** rather than creating the
file (`nano: /etc/nginx/sites-available/app: No such file or directory`), so the
player must `mkdir -p` the directory first — `mkdir` is already in the accepted
command list for step 9, and step 8's list gains `mkdir -p /etc/nginx/sites-available`.

Step 8's `configured` flag is set when the site file's content parses as a valid
nginx server block; `enabled` when the symlink exists in `sites-enabled/`.

### 4.10 Showing the player where they stand

The anti-goal says the player should not need the spec open. The design gives
every step a state predicate but no way to *observe* them, so a new command is
added to the server shell:

```
checklist
```

It prints the 11 steps with a done/not-done marker and a one-line hint for the
next incomplete step ("Step 5 — configure the firewall: allow the SSH port before
enabling"). It reads the same predicates that decide completion, so it can never
disagree with the win condition.

A `data/guides/lab_d2_001.txt` walkthrough is **not** added — the checklist plus
the per-command coaching covers it, and a written guide would duplicate the
source spec's content inside the game.

### 4.11 The clock during the challenge

**Decision:** the game clock **pauses** while the player is in the terminal
session and is rebased on exit, exactly as `teachers_room_4.py::inspect_computer`
already does for the NixOS shell.

The reasoning: this challenge is a 20–40 minute activity. If the clock ran, a
player doing everything correctly would lose most of their 1000 points to
`EXPLORATION_POINTS_PER_MINUTE = 12` purely for doing the intended thing. The
pause also matches the established pattern in the codebase, so there is one
consistent rule: **time spent in a terminal is not charged to the player.**

`inspect_server` therefore pauses the clock when it opens the shell and rebases
`session.duration.last_write` on exit, while still paused, so no terminal time
is ever charged.


### 4.12 Completion, flag, item, gate

On the win condition:

1. `flags["lab_server_provisioned"] = True` — the flag shows on the status screen
   alongside the existing challenge flags.
2. The awarded item is added to the player's inventory.
3. A "Server Provisioning Complete" screen is shown.

**The awarded item** (invented for this fiction, non-assembly so it does not
disturb the 11-part robot build):

```
"server_provisioning_certificate": {
    "name": "Server Provisioning Certificate",
    "description": "Cryptographic proof that the maze-server backend was correctly provisioned and hardened. Authorises the robot's neural link.",
    "is_assembly_part": false
}
```

**The gate** — `LabD2002.activate()` refuses while the flag is false:

> "The robot's neural link needs the maze-server backend provisioned first. Finish the server configuration in Lab D 2001."

The check happens **before** the Wi-Fi password prompt, so the player is never
asked for a password they cannot use.

## 5. What the builder still owns

- Exact command syntax accepted per step (how forgiving the parser is).
- Module-level structure inside `server_state.py` beyond the responsibilities above.
- The exact wording of coaching messages not fixed by the source spec.
- Whether `ServerShell` subclasses `VirtualShell` or composes it, provided
  Teacher Room 4's behavior and tests are unaffected.
- Test file layout and fixture design.
- How `ServerState` exposes the 11 step predicates (public methods, a list of
  `(name, done, hint)` tuples, or a small enum).

## 5.1 Decisions taken from the builder review

These were gaps the reviewer surfaced that do not need the player to decide:

| Question | Decision |
|---|---|
| SSH user flow / does `sudo` matter | SSH accepts any user and authenticates per user (§4.3). `sudo` requires `users[user].sudo`. |
| Firewall lockout recovery | Firewall config rolls back to pre-`enable` state on sever (§4.3). |
| SSH port change | Supported end to end, including `ssh -p` on the local shell (§4.3). |
| Fixed admin username | Arbitrary; state tracks `system.admin_user` (§4.5). |
| Persisted shape of `state["server"]` | One filesystem tree, richer nodes with `content` + derived `parsed` (§4.1). |
| Pre-existing server files | Fixed starting image, tabulated in §4.9. `nano` does not create files. |
| Backfilling existing saves | `State.normalize_state` backfills missing items and flags (§4.1). |
| Does the clock run during the challenge | No — it pauses and rebases, like Teacher Room 4 (§4.11). |
| Can the player see remaining steps | Yes — a `checklist` command on the server shell (§4.10). |

## 6. Risks

- **Scope.** 11 steps × ~25 commands × an editor is the largest single feature in
  the project. It should be built in slices, each slice ending green.
- **Raw-key handling across platforms.** Windows and POSIX report arrow keys
  differently; the shared helper must normalize them or the editor will misbehave
  on one platform.
- **Parser strictness.** Deciding "is this YAML valid" is genuinely hard. The
  builders should implement a deliberately narrow parser that checks the specific
  structure the game needs (indentation of the keys it cares about), not real YAML.
- **State bloat.** The `server` key in `user.json` is large. It is persisted on
  every autosave; this is acceptable but should be noted.
- **Two machines, one tree.** Because the local workstation and the server share
  one filesystem tree, a bug in path resolution could let the player read server
  files from the local machine. The builder must ensure `~` and the working
  directory are scoped to the current machine's home.

