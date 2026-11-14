# Server Configuration Challenge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an 11-step server-provisioning challenge playable through a terminal in Lab D 2001, gated on the robot's activation, awarding an item and setting a flag.

**Architecture:** The game's `state` dict gains a `server` section (plain JSON, persisted). A new `ServerState` class is a typed *view* over that dict — it owns the schema, the per-file config parsers, and the 11 step predicates. `src/utils/shell.py` gains a `ServerShell` that plays the challenge across two machines (local workstation → `maze-server` over SSH) with `sudo`, interactive sub-prompts, and the full command set. A new `src/utils/editor.py` provides a character-level nano-style modal editor with injected I/O, and `src/utils/keys.py` provides cross-platform normalized key reading shared by the editor and the guide pager.

**Tech Stack:** Python 3.12+, stdlib only (`shlex`, `termios`/`tty`, `msvcrt`, `dataclasses`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-14-server-configuration-challenge-design.md` (design doc; read §4 for every decision below). Source spec the design re-themes: `specs/server_configuration_game_spec.md`.

## Global Constraints

- **No new third-party dependencies.** Everything is stdlib.
- **Python 3.12+.** `mypy .` and `ruff check .` must both pass with zero errors.
- **The existing suite must stay green.** 219 tests currently pass; the 80% coverage floor in `pyproject.toml` must hold.
- **Teacher Room 4 must not regress.** `src/utils/shell.py`'s `VirtualShell` and `ShellResult` keep their current behavior and `tests/test_shell.py` keeps passing unchanged.
- **State is strict JSON** — primitives, lists, dicts only. No live objects in `state["server"]`.
- **Canonical ids are snake_case.** Room ids `lab_d2_001`/`lab_d2_002`; item ids `server_provisioning_certificate`.
- **Re-themed values** (fixed everywhere, including messages): server IP `10.11.7.42`, hostname `maze-server`, FQDN `maze-server.thuas.nl`, nginx root `/var/www/maze`, local workstation `thuas-workstation`, local shell user `player`.
- **Do not commit `data/user.json`** — the user's working tree stopped ignoring it in `.gitignore`; it is live player state.
- **Do not commit `specs/*`** — `.gitignore` now excludes it. The design doc copy in `docs/superpowers/specs/` is the tracked one.
- **Re-themed names, not the spec's originals.** `203.0.113.42`, `ubuntu-server`, `prod-server-01.example.com`, and `/var/www/app` must not appear in new code or messages.
- **Every shell command returns a `ShellResult`; nothing raises for player input.** Malformed input yields an error result.

## Review Focus

These are the input classes the spec implies but no task's happy-path tests cover. Each has a test in the task that owns the code.

1. **Unknown flag or wrong argument count on any server command** → error message, never an exception or a partial state change. *(Task 5)*
2. **Config file edited into invalid syntax** → the file's `parsed` block records `syntax_valid: false`, the step does not complete, and the game does not crash. *(Task 1)*
3. **`ufw enable` before the SSH port is allowed** → session severed with the broken-pipe message, firewall rolled back to its pre-`enable` state, and the challenge still completable. *(Task 7)*
4. **`systemctl reload sshd` after disabling root login with no admin key** → later `ssh` attempts fail with a clear message and the challenge stays winnable. *(Task 6)*
5. **Leaving the room or reloading the game mid-challenge** → every step's state, including parsed config fields, is restored exactly; the checklist still reflects it. *(Task 2)*
6. **An existing save with no `server` key, and no `lab_server_provisioned` flag, and no `server_provisioning_certificate` item** → loads without `KeyError`, and the new item/flag are backfilled. *(Task 2)*
7. **A shell command typed with a stray space, tab, or trailing argument** → handled the same as the clean form. *(Task 5)*

## File Structure

**Created**

| File | Responsibility |
|---|---|
| `src/server_state.py` | `ServerState` — typed view over `state["server"]`. Owns the schema, the default template, the per-file config parsers, and the 11 step predicates. Pure logic, no I/O. |
| `src/utils/keys.py` | `read_key()` — cross-platform single keypress reading, normalized to tokens (`"UP"`, `"CTRL_S"`, …) or the literal character. |
| `src/utils/editor.py` | `ModalEditor` — character-level modal editor with injected key reader and writer. |
| `tests/test_server_state.py` | `ServerState` schema, parsers, step predicates. |
| `tests/test_keys.py` | `read_key()` normalization for both platform encodings. |
| `tests/test_editor.py` | `ModalEditor` editing behaviour. |
| `tests/test_server_shell.py` | `ServerShell` commands, sub-prompts, traps, machine switching. |

**Modified**

| File | Change |
|---|---|
| `src/utils/shell.py` | `ShellResult` gains `prompt: str \| None = None`. Add `ServerShell`. `VirtualShell` untouched. |
| `src/state.py` | `server` property; `_PERSIST_KEYS` gains `"server"`; `__load_static` seeds `server` when absent; `__backfill_terminal_state` backfills the new item and flag. |
| `src/rooms/lab_d2_001.py` | `inspect_server()` runs the real terminal session. |
| `src/rooms/lab_d2_002.py` | `activate()` refuses until the server is provisioned. |
| `data/default.json` | `server` template, `lab_server_provisioned` flag, `server_provisioning_certificate` item. |
| `tests/test_lab.py` | Fix broken import (`Lab` → `LabD2002`) — pre-existing break from the room rename. |
| `docs/STATE_SCHEMA.md` | Document the `server` section, the new flag, the new item. |

---

### Task 1: `ServerState` — schema, parsers, step predicates

**Files:**
- Create: `src/server_state.py`
- Test: `tests/test_server_state.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `class ServerState` in `src/server_state.py`
    - `ServerState(data: dict[str, Any]) -> None`
    - `.data: dict[str, Any]` — the live dict (mutations are visible to the owner of `state["server"]`)
    - `.session -> dict[str, Any]` — `self.data["session"]`
    - `.filesystem -> dict[str, Any]` — `self.data["filesystem"]`
    - `.system -> dict[str, Any]` — `self.data["system"]`
    - `.steps() -> list[ServerStep]`
    - `.complete -> bool` — `all(step.done for step in self.steps())`
  - `@dataclass(frozen=True) class ServerStep` — fields `id: str`, `title: str`, `hint: str`, `done: bool`
  - `ServerState.default() -> dict[str, Any]` — static/class method returning a fresh default template (deep-copied on each call)
  - `ServerState.set_file_content(path: str, content: str) -> None` — writes `content` into the file node at `path` and re-derives its `parsed` block
  - Module-level parsers, each `(content: str, ...) -> dict[str, Any]`:
    - `parse_sshd_config(content: str) -> dict[str, Any]` → `{"PermitRootLogin": str, "PasswordAuthentication": str, "Port": int, "syntax_valid": bool}`
    - `parse_hosts(content: str, hostname: str) -> dict[str, Any]` → `{"mapped_fqdn": bool}`
    - `parse_netplan(content: str, ip: str) -> dict[str, Any]` → `{"static_ip_set": bool, "syntax_valid": bool}`
    - `parse_nginx_site(content: str) -> dict[str, Any]` → `{"configured": bool, "syntax_valid": bool}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_state.py
import copy

import pytest

from src.server_state import ServerState, parse_hosts, parse_netplan, parse_nginx_site, parse_sshd_config


def test_default_template_has_session_filesystem_and_system():
    template = ServerState.default()
    assert set(template) == {"session", "filesystem", "system"}
    assert template["session"]["machine"] == "thuas-workstation"
    assert template["session"]["user"] == "player"
    assert template["session"]["cwd"] == "/home/player"
    assert template["session"]["prompt_symbol"] == "$"
    assert template["session"]["connected_via_ssh"] is False
    assert template["session"]["pending_prompt"] is None
    assert template["system"]["ip_address"] == "10.11.7.42"
    assert template["system"]["hostname"] == "maze-server"
    assert template["system"]["known_hosts"] == []
    assert template["system"]["pkg_index_updated"] is False
    assert template["system"]["pkg_upgraded"] is False
    assert template["system"]["ntp_synced"] is False
    assert template["system"]["admin_user"] is None
    assert template["system"]["users"] == {"root": {"sudo": True, "has_ssh_key": True}}
    assert template["system"]["firewall"] == {
        "active": False,
        "default_incoming": "allow",
        "default_outgoing": "allow",
        "allowed_ports": [],
    }
    assert template["system"]["services"]["sshd"] == {
        "installed": True, "running": True, "enabled": True, "port": 22,
    }
    assert template["system"]["services"]["nginx"] == {
        "installed": False, "running": False, "enabled": False, "port": 80,
    }
    assert template["system"]["health_verified"] == {
        "service_status_checked": False, "ports_checked": False, "logs_or_http_checked": False,
    }


def test_default_template_has_the_initial_server_image():
    filesystem = ServerState.default()["filesystem"]
    assert filesystem["/etc/ssh/sshd_config"]["type"] == "file"
    assert filesystem["/etc/ssh/sshd_config"]["perms"] == "600"
    assert filesystem["/etc/ssh/sshd_config"]["owner"] == "root:root"
    assert filesystem["/etc/hosts"]["type"] == "file"
    assert filesystem["/etc/netplan/50-cloud-init.yaml"]["type"] == "file"
    assert filesystem["/etc/nginx/sites-enabled"]["type"] == "dir"
    assert filesystem["/home/player/.ssh/id_ed25519"]["type"] == "file"
    assert filesystem["/home/player/.ssh/id_ed25519"]["owner"] == "player:player"
    # These must NOT exist yet: the player creates them.
    assert "/etc/nginx/sites-available/app" not in filesystem
    assert "/var/www/maze" not in filesystem


def test_default_template_is_not_shared_between_calls():
    first = ServerState.default()
    first["system"]["hostname"] = "changed"
    assert ServerState.default()["system"]["hostname"] == "maze-server"


def test_parse_sshd_config_reads_directives_and_validates_syntax():
    parsed = parse_sshd_config("PermitRootLogin no\nPasswordAuthentication no\nPort 2222\n")
    assert parsed == {
        "PermitRootLogin": "no",
        "PasswordAuthentication": "no",
        "Port": 2222,
        "syntax_valid": True,
    }


def test_parse_sshd_config_marks_missing_directive_as_invalid():
    parsed = parse_sshd_config("PermitRootLogin no\n")
    assert parsed["syntax_valid"] is False
    assert parsed["PasswordAuthentication"] == ""
    assert parsed["Port"] == 22


def test_parse_hosts_reports_whether_the_fqdn_is_mapped():
    assert parse_hosts("127.0.0.1 localhost\n", "maze-server.thuas.nl") == {"mapped_fqdn": False}
    assert parse_hosts(
        "127.0.0.1 localhost\n127.0.1.1 maze-server.thuas.nl maze-server\n",
        "maze-server.thuas.nl",
    ) == {"mapped_fqdn": True}


def test_parse_netplan_reports_static_ip_and_syntax():
    good = "network:\n  version: 2\n  ethernets:\n    eth0:\n      addresses:\n        - 10.11.7.42/24\n"
    assert parse_netplan(good, "10.11.7.42") == {"static_ip_set": True, "syntax_valid": True}
    bad = "network:\n  version: 2\n  ethernets:\n   eth0:\n      dhcp4: true\n"
    assert parse_netplan(bad, "10.11.7.42") == {"static_ip_set": False, "syntax_valid": False}


def test_parse_nginx_site_requires_a_server_block():
    assert parse_nginx_site("server {\n  listen 80;\n  root /var/www/maze;\n}\n") == {
        "configured": True, "syntax_valid": True,
    }
    assert parse_nginx_site("server {\n  listen 80;\n  root /var/www/maze\n") == {
        "configured": False, "syntax_valid": False,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server_state.py -q --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.server_state'`

- [ ] **Step 3: Implement `src/server_state.py`**

Module docstring: `"""Typed view over the game state's ``server`` section: schema, config parsers, step predicates."""`

```python
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

SERVER_IP = "10.11.7.42"
SERVER_HOSTNAME = "maze-server"
SERVER_FQDN = "maze-server.thuas.nl"
NGINX_ROOT = "/var/www/maze"
LOCAL_MACHINE = "thuas-workstation"
LOCAL_USER = "player"
```

`ServerState.default()` returns a deep copy of a module-level `_DEFAULT_TEMPLATE` dict built literally with the keys asserted in the test. The `filesystem` map is **flat**, keyed by absolute path, with two node shapes:

- file node: `{"type": "file", "content": str, "perms": str, "owner": str, "parsed": dict}`
- directory node: `{"type": "dir", "perms": str, "owner": str}`

Required initial paths and their content:

| Path | Node | Initial content |
|---|---|---|
| `/` | dir 755 root:root | — |
| `/etc` | dir 755 root:root | — |
| `/etc/ssh` | dir 755 root:root | — |
| `/etc/ssh/sshd_config` | file 600 root:root | `PermitRootLogin yes\nPasswordAuthentication yes\nPort 22\n` |
| `/etc/hosts` | file 644 root:root | `127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server\n` |
| `/etc/netplan` | dir 755 root:root | — |
| `/etc/netplan/50-cloud-init.yaml` | file 644 root:root | `network:\n  version: 2\n  ethernets:\n    eth0:\n      dhcp4: true\n` |
| `/etc/nginx` | dir 755 root:root | — |
| `/etc/nginx/sites-available` | dir 755 root:root | — |
| `/etc/nginx/sites-enabled` | dir 755 root:root | — |
| `/home` | dir 755 root:root | — |
| `/home/player` | dir 755 player:player | — |
| `/home/player/.ssh` | dir 700 player:player | — |
| `/home/player/.ssh/id_ed25519` | file 600 player:player | `-----BEGIN OPENSSH PRIVATE KEY-----\nplayer-lab-key\n-----END OPENSSH PRIVATE KEY-----\n` |
| `/root` | dir 700 root:root | — |
| `/root/.ssh` | dir 700 root:root | — |
| `/root/.ssh/authorized_keys` | file 600 root:root | `` (empty) |
| `/var` | dir 755 root:root | — |
| `/var/log` | dir 755 root:root | — |
| `/var/log/nginx` | dir 755 root:root | — |
| `/var/log/nginx/access.log` | file 644 root:root | `` (empty) |
| `/var/www` | dir 755 root:root | — |

Each file node's `parsed` block is populated by calling the matching parser on its `content` (see the parser signatures above); `parse_hosts` is called with `SERVER_FQDN` and `parse_netplan` with `SERVER_IP`.

Parsers (narrow by design — they check only the structure the game needs, never full YAML/sshd/nginx validity):

- `parse_sshd_config(content)`: split on newlines, ignore blank lines and lines starting with `#`. Accept only `Key Value` lines where `Key` is one of `PermitRootLogin`, `PasswordAuthentication`, `Port`. Any other non-comment line, or a duplicate key, or a `Port` that is not a positive integer → `syntax_valid: False`. A valid file with a missing required key → `syntax_valid: False` and that key's value `""`. `Port` defaults to `22` when the key is absent but the file is otherwise valid. `Port` is `int` when present and valid, else `22`.
- `parse_hosts(content, hostname)`: `mapped_fqdn` is `True` when some line's whitespace-separated fields include `hostname` and the line's first field is `127.0.1.1`.
- `parse_netplan(content, ip)`: `syntax_valid` is `True` when the text contains a `network:` key at the start of a line and every following line's indentation is a multiple of two spaces and the file has no tab characters. `static_ip_set` is `True` when `syntax_valid` and the text contains the literal `ip` (e.g. `10.11.7.42`) inside an `addresses:` block.
- `parse_nginx_site(content)`: `syntax_valid` is `True` when the text contains a `server {` block, a matching `}` at the end, and every non-empty line inside ends with `;` or is `server {` or `}`. `configured` is `True` when `syntax_valid` and the text contains `root /var/www/maze;` and `listen 80;`.

`ServerState.set_file_content(path, content)`: set `filesystem[path]["content"] = content`, then re-derive that file's `parsed` block with the matching parser, using `self.system.get("hostname", SERVER_FQDN)` for hosts and `self.system.get("ip_address", SERVER_IP)` for netplan. Writing to an unknown path raises `KeyError` — callers check first.

`ServerState.steps()` returns the 11 `ServerStep`s in order, each `done` computed from state:

| id | title | done when |
|---|---|---|
| `ssh` | SSH connect | `session["connected_via_ssh"]` is `True` and `SERVER_IP` in `system["known_hosts"]` |
| `packages` | System packages | `system["pkg_index_updated"]` and `system["pkg_upgraded"]` are both `True` |
| `admin_user` | Admin user | `system["admin_user"]` is not `None` and that user has `sudo` and `has_ssh_key` both `True` |
| `ssh_hardening` | SSH hardening | `parsed` of `/etc/ssh/sshd_config` has `PermitRootLogin == "no"`, `PasswordAuthentication == "no"`, `syntax_valid` `True`, and `system["services"]["sshd"]["port"]` equals the file's `Port` |
| `firewall` | Firewall | `system["firewall"]["active"]` is `True`, `default_incoming == "deny"`, `default_outgoing == "allow"`, and the sshd port plus `80` and `443` are all in `allowed_ports` |
| `host_network` | Host and network | `system["hostname"] == SERVER_FQDN`, `parsed` of `/etc/hosts` has `mapped_fqdn` `True`, and `parsed` of `/etc/netplan/50-cloud-init.yaml` has `static_ip_set` `True` |
| `time_sync` | Time sync | `system["ntp_synced"]` is `True` |
| `nginx` | Core service | `system["services"]["nginx"]["installed"]` is `True`, and `/etc/nginx/sites-available/app` exists with `parsed` `configured` and `syntax_valid` both `True`, and the symlink `/etc/nginx/sites-enabled/app` exists |
| `permissions` | Directory permissions | `/var/www/maze` exists with `owner` ending `:www-data` and `perms` in `("755", "750")` |
| `daemons` | Daemons | `system["services"]["nginx"]["enabled"]` and `["running"]` are both `True` |
| `verification` | Verification | all three `system["health_verified"]` flags are `True` |

Each step's `hint` is a one-line coaching string, e.g. `ssh` → `"Step 1 — connect: ssh -i ~/.ssh/id_ed25519 root@10.11.7.42"`, `firewall` → `"Step 5 — allow the SSH port with ufw allow <port>/tcp before ufw enable"`.

Reading a missing path or missing `parsed` key must not raise: use `.get()` chains that default to "not done".

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server_state.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/server_state.py tests/test_server_state.py
git commit -m "feat(server): add ServerState schema, config parsers and step predicates"
```

---

### Task 2: Persist the `server` section in the game state

**Files:**
- Modify: `src/state.py` — `_PERSIST_KEYS` (line 27), `__load_static` (line 155), `__backfill_terminal_state` (line 203), plus a new `server` property after `items` (line 111)
- Modify: `data/default.json` — add `server`, `lab_server_provisioned`, `server_provisioning_certificate`
- Modify: `tests/test_state.py`
- Modify: `tests/test_lab.py` — fix the broken import
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `ServerState.default() -> dict[str, Any]` from `src.server_state` (Task 1)
- Produces:
  - `State.server -> ServerState` — property; returns `ServerState(self.data["server"])`, seeding `self.data["server"] = ServerState.default()` first if the key is absent
  - `"server"` added to `State._PERSIST_KEYS`
  - `data/default.json` gains a top-level `"server"` key equal to `ServerState.default()`, a `"lab_server_provisioned": false` flag, and a `"server_provisioning_certificate"` item

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
def test_state_seeds_and_exposes_server_state(oop_state):
    assert isinstance(oop_state.server, ServerState)
    assert oop_state.server.system["ip_address"] == "10.11.7.42"


def test_persist_writes_the_server_section(oop_state):
    oop_state.server.system["hostname"] = "maze-server.thuas.nl"
    oop_state.persist()
    payload = json.loads(oop_state.USER_STATE_PATH.read_text(encoding="utf-8"))
    assert payload["server"]["system"]["hostname"] == "maze-server.thuas.nl"


def test_load_restores_the_server_section(oop_state, tmp_path):
    oop_state.server.system["pkg_upgraded"] = True
    oop_state.persist()
    reloaded = State()
    reloaded.USER_STATE_PATH = oop_state.USER_STATE_PATH
    reloaded.data = json.loads(oop_state.USER_STATE_PATH.read_text(encoding="utf-8"))
    reloaded.normalize_state()
    assert reloaded.server.system["pkg_upgraded"] is True


def test_normalize_backfills_the_new_flag_and_item(oop_state):
    del oop_state.data["flags"]["lab_server_provisioned"]
    del oop_state.data["items"]["server_provisioning_certificate"]

    oop_state.normalize_state()

    assert oop_state.flags["lab_server_provisioned"] is False
    assert oop_state.items["server_provisioning_certificate"]["name"] == "Server Provisioning Certificate"
```

Add the import at the top of `tests/test_state.py`: `from src.server_state import ServerState`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -q --no-cov`
Expected: FAIL — `AttributeError: 'State' object has no attribute 'server'`

- [ ] **Step 3: Implement the state changes**

In `src/state.py`:

- Add `"server"` to `_PERSIST_KEYS` (after `"items"`).
- Add the property after the `items` property:
  ```python
  @property
  def server(self) -> ServerState:
      """The server-provisioning challenge state."""
      if "server" not in self.data:
          self.data["server"] = ServerState.default()
      return ServerState(self.data["server"])
  ```
- Import `from src.server_state import ServerState` at the top of `src/state.py`.
- In `__load_static`, after the rooms/items seeding, add:
  ```python
  if "server" not in self.data:
      self.data["server"] = ServerState.default()
  ```
- In `__backfill_terminal_state`, add:
  ```python
  default = json.loads(self.DEFAULT_GAME_STATE_PATH.read_text(encoding="utf-8"))
  for flag, value in default.get("flags", {}).items():
      self.data.setdefault("flags", {}).setdefault(flag, value)
  for item_id, meta in default.get("items", {}).items():
      self.data.setdefault("items", {}).setdefault(item_id, meta)
  ```

In `data/default.json`:

- Add `"server"` as a top-level key whose value equals `ServerState.default()` — copy the exact template from `src/server_state.py` (same keys, same values).
- Add `"lab_server_provisioned": false` to `flags`.
- Add to `items`:
  ```json
  "server_provisioning_certificate": {
      "name": "Server Provisioning Certificate",
      "description": "Cryptographic proof that the maze-server backend was correctly provisioned and hardened. Authorises the robot's neural link.",
      "is_assembly_part": false
  }
  ```

In `tests/test_lab.py`, change `from src.rooms.lab_d2_002 import Lab` to `from src.rooms.lab_d2_002 import LabD2002` and update the two `Lab` references in `_score` to `LabD2002` (the private method is `_LabD2002__calculate_score`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py tests/test_lab.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Run the whole suite to check for regressions**

Run: `python -m pytest -q --no-cov`
Expected: PASS — all previously passing tests plus the new ones.

- [ ] **Step 6: Commit**

```bash
git add src/state.py data/default.json tests/test_state.py tests/test_lab.py
git commit -m "feat(state): persist the server challenge section and backfill new flag and item"
```

---

### Task 3: `src/utils/keys.py` — normalized cross-platform key reading

**Files:**
- Create: `src/utils/keys.py`
- Test: `tests/test_keys.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `src/utils/keys.py::read_key(read: Callable[[], str] | None = None) -> str`
    - `read` is an optional injected raw-character reader. `None` means "use the platform default".
    - Returns one of the tokens `"UP"`, `"DOWN"`, `"LEFT"`, `"RIGHT"`, `"HOME"`, `"END"`, `"BACKSPACE"`, `"DELETE"`, `"ENTER"`, `"TAB"`, `"ESC"`, `"CTRL_S"`, `"CTRL_X"`, or a single literal character.
  - Module constants: `KEY_UP`, `KEY_DOWN`, `KEY_LEFT`, `KEY_RIGHT`, `KEY_HOME`, `KEY_END`, `KEY_BACKSPACE`, `KEY_DELETE`, `KEY_ENTER`, `KEY_TAB`, `KEY_ESC`, `KEY_CTRL_S`, `KEY_CTRL_X` — each the token string above.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_keys.py
from src.utils.keys import KEY_CTRL_S, KEY_DOWN, KEY_ENTER, KEY_LEFT, KEY_RIGHT, KEY_UP, read_key


def test_literal_characters_pass_through():
    assert read_key(lambda: "a") == "a"
    assert read_key(lambda: "q") == "q"


def test_posix_escape_sequences_are_normalized():
    assert read_key(iter(["\x1b", "[", "A"]).__next__) == KEY_UP
    assert read_key(iter(["\x1b", "[", "B"]).__next__) == KEY_DOWN
    assert read_key(iter(["\x1b", "[", "C"]).__next__) == KEY_RIGHT
    assert read_key(iter(["\x1b", "[", "D"]).__next__) == KEY_LEFT
    assert read_key(iter(["\x1b", "[", "H"]).__next__) == "HOME"
    assert read_key(iter(["\x1b", "[", "F"]).__next__) == "END"
    assert read_key(iter(["\x1b", "[", "3", "~"]).__next__) == "DELETE"


def test_windows_prefix_sequences_are_normalized():
    assert read_key(iter(["\xe0", "H"]).__next__) == KEY_UP
    assert read_key(iter(["\xe0", "P"]).__next__) == KEY_DOWN
    assert read_key(iter(["\xe0", "K"]).__next__) == KEY_LEFT
    assert read_key(iter(["\xe0", "M"]).__next__) == KEY_RIGHT
    assert read_key(iter(["\xe0", "G"]).__next__) == "HOME"
    assert read_key(iter(["\xe0", "O"]).__next__) == "END"
    assert read_key(iter(["\xe0", "S"]).__next__) == "DELETE"


def test_control_characters_are_normalized():
    assert read_key(lambda: "\r") == KEY_ENTER
    assert read_key(lambda: "\n") == KEY_ENTER
    assert read_key(lambda: "\x08") == "BACKSPACE"
    assert read_key(lambda: "\x7f") == "BACKSPACE"
    assert read_key(lambda: "\t") == "TAB"
    assert read_key(lambda: "\x1b") == "ESC"
    assert read_key(lambda: "\x13") == KEY_CTRL_S
    assert read_key(lambda: "\x18") == "CTRL_X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_keys.py -q --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.utils.keys'`

- [ ] **Step 3: Implement `src/utils/keys.py`**

Module docstring: `"""Cross-platform single-key reading, normalized to stable tokens."""`

Define the token constants listed in Interfaces.

`read_key(read=None)`:

1. If `read` is `None`, build the platform reader:
   - `sys.platform == "win32"`: `import msvcrt` → `msvcrt.getwch`
   - otherwise: `import termios, tty` → set the terminal to raw mode, `sys.stdin.read(1)`, restore the terminal in a `finally`
2. Read one character `ch`.
3. If `ch` is `"\x1b"` (POSIX escape): read up to two more characters.
   - If the next is `"["`, read one more and map `"A"`→`KEY_UP`, `"B"`→`KEY_DOWN`, `"C"`→`KEY_RIGHT`, `"D"`→`KEY_LEFT`, `"H"`→`KEY_HOME`, `"F"`→`KEY_END`, `"3"`→ read one more; if that is `"~"` → `KEY_DELETE`.
   - If the next is `"O"`, read one more and map `"H"`→`KEY_HOME`, `"F"`→`KEY_END`.
   - Otherwise return `KEY_ESC`.
4. If `ch` is `"\xe0"` or `"\x00"` (Windows prefix): read one more and map `"H"`→`KEY_UP`, `"P"`→`KEY_DOWN`, `"K"`→`KEY_LEFT`, `"M"`→`KEY_RIGHT`, `"G"`→`KEY_HOME`, `"O"`→`KEY_END`, `"S"`→`KEY_DELETE`; anything else → that character.
5. Otherwise map control characters: `"\r"`/`"\n"`→`KEY_ENTER`, `"\x08"`/`"\x7f"`→`KEY_BACKSPACE`, `"\t"`→`KEY_TAB`, `"\x13"`→`KEY_CTRL_S`, `"\x18"`→`KEY_CTRL_X`, `"\x1b"`→`KEY_ESC` (already handled above), else return `ch` unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_keys.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/keys.py tests/test_keys.py
git commit -m "feat(shell): add cross-platform normalized key reading"
```

---

### Task 4: `src/utils/editor.py` — character-level modal editor

**Files:**
- Create: `src/utils/editor.py`
- Test: `tests/test_editor.py`

**Interfaces:**
- Consumes: `read_key` from `src.utils.keys` (Task 3)
- Produces:
  - `class ModalEditor` in `src/utils/editor.py`
    - `ModalEditor(text: str, read_key: Callable[[], str] | None = None, write: Callable[[str], None] | None = None, title: str = "") -> None`
    - `.run() -> tuple[bool, str]` — returns `(saved, final_text)`. `saved` is `True` only when the user pressed Ctrl+S.
    - `read_key` defaults to `src.utils.keys.read_key`; `write` defaults to `print`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_editor.py
from src.utils.editor import ModalEditor
from src.utils.keys import KEY_BACKSPACE, KEY_CTRL_S, KEY_CTRL_X, KEY_DOWN, KEY_END, KEY_ENTER, KEY_HOME, KEY_LEFT, KEY_RIGHT, KEY_UP


def run_editor(text, keys):
    written = []
    editor = ModalEditor(
        text,
        read_key=iter(keys).__next__,
        write=written.append,
    )
    saved, result = editor.run()
    return saved, result, "".join(written)


def test_typing_inserts_characters():
    saved, result, _ = run_editor("ab", ["c", "d"])
    assert saved is False
    assert result == "abcd"


def test_backspace_deletes_the_character_before_the_cursor():
    _, result, _ = run_editor("abc", [KEY_BACKSPACE])
    assert result == "ab"


def test_arrow_keys_move_the_cursor():
    _, result, _ = run_editor("abc", [KEY_LEFT, "X"])
    assert result == "abXc"


def test_enter_inserts_a_newline():
    _, result, _ = run_editor("ab", [KEY_ENTER, "c"])
    assert result == "ab\nc"


def test_home_and_end_jump_to_the_line_edges():
    _, result, _ = run_editor("abc", [KEY_HOME, "X"])
    assert result == "Xabc"
    _, result, _ = run_editor("abc", [KEY_END, "X"])
    assert result == "abcX"


def test_down_moves_to_the_next_line():
    _, result, _ = run_editor("ab\ncd", [KEY_DOWN, "X"])
    assert result == "ab\nXcd"


def test_ctrl_s_saves_and_ctrl_x_discards():
    saved, result, _ = run_editor("ab", ["c", KEY_CTRL_S])
    assert saved is True
    assert result == "abc"

    saved, result, _ = run_editor("ab", ["c", KEY_CTRL_X])
    assert saved is False
    assert result == "ab"


def test_editor_redraws_with_escape_sequences():
    _, _, written = run_editor("ab", ["c"])
    assert "\x1b[" in "".join(written)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_editor.py -q --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.utils.editor'`

- [ ] **Step 3: Implement `src/utils/editor.py`**

Module docstring: `"""A nano-style character-level modal editor with injected input and output."""`

```python
from __future__ import annotations

from typing import Callable

from src.utils.keys import (
    KEY_BACKSPACE, KEY_CTRL_S, KEY_CTRL_X, KEY_DELETE, KEY_DOWN, KEY_END,
    KEY_ENTER, KEY_ESC, KEY_HOME, KEY_LEFT, KEY_RIGHT, KEY_TAB, KEY_UP,
    read_key,
)
```

`ModalEditor.__init__(text, read_key=None, write=None, title="")` stores the buffer as a list of lines (`text.split("\n")`), the cursor as `(row, col)`, and the injected `read_key`/`write` (defaulting to `src.utils.keys.read_key` and `print`).

`run()` loops until the user exits:

- Render: `write("\x1b[H\x1b[2J")` to clear, then the title line, then each buffer line, then a status line reading `"^S save  ^X exit"`. Position the cursor with `write(f"\x1b[{row + 3};{col + 1}H")`.
- Read one key and apply it:
  - literal character (length 1, printable): insert at the cursor, advance the cursor.
  - `KEY_LEFT`/`KEY_RIGHT`: move the cursor within the line, clamped to the line's length.
  - `KEY_UP`/`KEY_DOWN`: move to the previous/next line, clamping the column to that line's length.
  - `KEY_HOME`/`KEY_END`: column to `0` / line length.
  - `KEY_BACKSPACE`: delete the character before the cursor if the column is greater than 0; if the column is 0 and the row is greater than 0, join this line onto the end of the previous line and move the cursor to the join point.
  - `KEY_DELETE`: delete the character at the cursor.
  - `KEY_ENTER`: split the line at the cursor into two lines.
  - `KEY_TAB`: insert a literal tab character.
  - `KEY_CTRL_S`: save — `return True, "\n".join(self._lines)`.
  - `KEY_CTRL_X`: discard — `return False, "\n".join(self._lines)` (the buffer is discarded by the caller, so the returned text is the edited buffer but `saved` is `False`).
  - `KEY_ESC`: same as `KEY_CTRL_X`.
- After every key, re-render.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_editor.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/editor.py tests/test_editor.py
git commit -m "feat(editor): add nano-style character-level modal editor"
```

---

### Task 5: `ServerShell` — core shell, file commands, privilege, sub-prompts

**Files:**
- Modify: `src/utils/shell.py` — `ShellResult` (line 29) and a new `ServerShell` class appended
- Test: `tests/test_server_shell.py`

**Interfaces:**
- Consumes: `ServerState` from `src.server_state` (Task 1); `read_key` from `src.utils.keys` (Task 3)
- Produces:
  - `ShellResult` gains a field `prompt: str | None = None` — the text of a sub-prompt the shell is waiting on. Existing fields and their defaults are unchanged, so `ShellResult()` still equals `ShellResult()` and `tests/test_shell.py` is unaffected.
  - `class ServerShell` in `src/utils/shell.py`
    - `ServerShell(state: ServerState, read_line: Callable[[str], str] | None = None, write: Callable[[str], None] | None = None, editor: Callable[[str], tuple[bool, str]] | None = None) -> None`
      - `read_line` defaults to `input`; `write` defaults to `print`; `editor` defaults to opening a `ModalEditor` built on `read_key`/`write` (from `src.utils.keys` and `src.utils.editor`).
    - `.execute(command: str) -> ShellResult` — parse with `shlex.split` (posix mode), dispatch on the first token to `_cmd_<name>`, and never raise for player input.
    - `.answer(text: str) -> ShellResult` — resolves the pending sub-prompt recorded in `state.session["pending_prompt"]`. Task 5 implements the mechanism and the `ssh_host_key` kind; Task 6 adds the `apt_confirm` and `adduser_password` kinds.
    - The dispatcher resolves a command by its first token (`getattr(self, f"_cmd_{token}")`), so alternative spellings need aliases: `_cmd_apt_get = _cmd_apt`, `_cmd_vim = _cmd_nano`, `_cmd_netstat = _cmd_ss`. A multi-token command such as `sshd -t` is handled by one method that inspects its arguments — the method name is the first token only.
    - `.prompt -> str` — the rendered prompt for the current machine.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_shell.py
import pytest

from src.server_state import ServerState
from src.utils.shell import ServerShell, ShellResult


@pytest.fixture
def server_state():
    return ServerState(ServerState.default())


@pytest.fixture
def shell(server_state):
    lines = []
    return ServerShell(
        server_state,
        read_line=lambda prompt="": "",
        write=lines.append,
        editor=lambda text: (True, text),
    )


def test_execute_reports_unknown_commands(shell):
    assert shell.execute("frobnicate").output == "bash: frobnicate: command not found"


def test_execute_reports_unmatched_quotes(shell):
    assert shell.execute('cat "unterminated').output == "bash: syntax error: unmatched quote"


def test_empty_command_does_nothing(shell):
    assert shell.execute("") == ShellResult()


def test_prompt_shows_the_local_workstation(shell):
    assert shell.prompt == "player@thuas-workstation:~$"


def test_pwd_and_cd_navigate_the_tree(shell):
    assert shell.execute("pwd").output == "/home/player"
    assert shell.execute("cd /etc").output == ""
    assert shell.execute("pwd").output == "/etc"
    assert shell.execute("cd ..").output == ""
    assert shell.execute("pwd").output == "/"


def test_ls_lists_a_directory(shell):
    output = shell.execute("ls /etc/ssh").output
    assert "sshd_config" in output


def test_cat_prints_file_contents(shell):
    output = shell.execute("cat /etc/ssh/sshd_config").output
    assert "PermitRootLogin yes" in output


def test_cat_reports_a_missing_file(shell):
    assert "No such file or directory" in shell.execute("cat /etc/nope").output


def test_whoami_and_groups(shell):
    assert shell.execute("whoami").output == "player"
    assert "sudo" in shell.execute("groups").output


def test_sudo_is_required_for_privileged_commands(shell):
    result = shell.execute("apt update")
    assert result.output == "Permission denied (are you root?)"
    assert shell.state.system["pkg_index_updated"] is False


def test_unknown_flags_do_not_change_state(shell):
    result = shell.execute("ls --bogus")
    assert "unrecognized option" in result.output


def test_trailing_whitespace_is_tolerated(shell):
    assert shell.execute("pwd   ").output == "/home/player"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: FAIL with `ImportError: cannot import name 'ServerShell' from 'src.utils.shell'`

- [ ] **Step 3: Implement the `ServerShell` core in `src/utils/shell.py`**

Add to `ShellResult`:

```python
    prompt: str | None = None
```

Append `class ServerShell` to `src/utils/shell.py`:

- `__init__(state, read_line=None, write=None, editor=None)`: store the injected callables (`read_line` defaults to `input`, `write` defaults to `print`). The default `editor` builds `ModalEditor(text, read_key=read_key, write=write)` and returns `editor.run()`; import `ModalEditor` lazily inside the default so `src.utils.shell` does not import the editor at module load.

- `.prompt -> str`: read `state.session`. The machine is `state.session["machine"]`; the user is `state.session["user"]`; the cwd is `state.session["cwd"]`. The home directory is `/root` when the user is `root`, else `/home/<user>`. Render `<user>@<machine>:<display_cwd><symbol>` where `<display_cwd>` is `~` at home, `~/<suffix>` below home, else the absolute path; `<symbol>` is `state.session["prompt_symbol"]`. For the local workstation that yields `player@thuas-workstation:~$`; on the server as root, `root@maze-server:/root#`.

- `execute(command)`: if `state.session["pending_prompt"]` is not `None`, treat the command as the answer to that prompt and delegate to `answer(command)`. Otherwise `shlex.split(command, posix=True)`; on `ValueError` return `ShellResult(output="bash: syntax error: unmatched quote")`. An empty token list returns `ShellResult()`. Dispatch to `getattr(self, f"_cmd_{name}", None)`; when it is `None`, return `ShellResult(output=f"bash: {name}: command not found")`. The handler's `ShellResult` is returned unchanged.

- `answer(text)`: read `pending = state.session["pending_prompt"]`, clear `state.session["pending_prompt"] = None`, and dispatch on `pending["kind"]` to the handler that continues the interrupted command. Kinds are `"ssh_host_key"`, `"apt_confirm"`, `"ufw_confirm"`, and `"adduser_password"`. Each handler returns a `ShellResult`.

- Filesystem access, over the flat path→node map in `state.filesystem`:
  - `_resolve(path)`: expand `~` to the current home, make a relative path relative to `state.session["cwd"]`, normalize `..`/`.` segments, and return an absolute path with a single leading `/`.
  - `_node(path)`: return the node dict for an exact path, or `None` if the path is absent.
  - `_children(path)`: every filesystem path whose parent directory is `path`, sorted.
  - `_is_dir(path)`: the node at `path` is a dir node, or `path` has children.

- Commands (all returning `ShellResult`):
  - `_cmd_pwd` → `state.session["cwd"]`
  - `_cmd_cd` — zero or one argument (default `~`); more than one → `"cd: too many arguments"`; unknown path → `"cd: no such file or directory: <path>"`; not a directory → `"cd: not a directory: <path>"`; success sets `state.session["cwd"]`.
  - `_cmd_ls` — flags `-a` (include dotfiles) and `-l` (long form); one or more path arguments default to `.`; an unknown path yields `"ls: cannot access '<path>': No such file or directory"`; long form shows mode, owner, size, and name.
  - `_cmd_cat` — one or more files; each unknown path yields `"cat: <path>: No such file or directory"`; a directory yields `"cat: <path>: Is a directory"`; otherwise the content is printed and the path is recorded in `read_paths`.
  - `_cmd_whoami` → `state.session["user"]`
  - `_cmd_groups` → the user's groups; `root` → `"root sudo"`, a non-root user with `sudo` → `"<user> sudo"`, otherwise just `"<user>"`.
  - `_cmd_help` → the list of supported commands.
  - `_cmd_clear` → `ShellResult(clear_requested=True)`
  - `_cmd_exit` → on the local workstation, `ShellResult(exit_requested=True)`. On the server it must instead return the player to the workstation; Task 6 replaces that behaviour once the machine switch exists.

- Privilege: a helper `_require_root() -> bool` returning `False` when `state.session["user"] != "root"`. Every command that touches `/etc`, packages, the firewall, or services calls it first and returns `ShellResult(output="Permission denied (are you root?)")` when it fails. `sudo` is handled in `execute` as a prefix: if the first token is `sudo`, drop it, temporarily set the session user to `root` for the duration of the command, and restore it afterwards. `sudo` on a machine where the current user has no `sudo` entry in `state.system["users"]` → `"sudo: <user> is not in the sudoers file. This incident will be reported."`

- The state tree is shared between machines (the local workstation lives under `/home/player`, the server under `/root` and `/etc`), so the same `ServerShell` instance serves both; `state.session["machine"]` decides which one the prompt shows.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Run the whole suite to check for regressions**

Run: `python -m pytest -q --no-cov`
Expected: PASS — `tests/test_shell.py` unchanged and still green.

- [ ] **Step 6: Commit**

```bash
git add src/utils/shell.py tests/test_server_shell.py
git commit -m "feat(shell): add ServerShell core with file commands and privilege checks"
```

---

### Task 6: `ServerShell` — SSH, users, packages, services

**Files:**
- Modify: `src/utils/shell.py` — add commands to `ServerShell`
- Modify: `tests/test_server_shell.py`

**Interfaces:**
- Consumes: `ServerShell` from Task 5, `ServerState` from Task 1
- Produces: additional `ServerShell` commands, listed in Step 3

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server_shell.py`:

```python
def test_ssh_to_the_server_prompts_for_the_host_key(shell):
    result = shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    assert result.prompt is not None
    assert "Are you sure you want to continue connecting" in result.prompt
    assert shell.state.session["connected_via_ssh"] is False


def test_answering_yes_accepts_the_host_key(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    assert shell.state.session["connected_via_ssh"] is True
    assert shell.state.session["machine"] == "maze-server"
    assert shell.state.session["user"] == "root"
    assert shell.state.session["cwd"] == "/root"
    assert shell.state.session["prompt_symbol"] == "#"
    assert "10.11.7.42" in shell.state.system["known_hosts"]


def test_typing_y_reprompts_for_the_full_word(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    result = shell.answer("y")
    assert result.prompt is not None
    assert "Please type 'yes', 'no' or the fingerprint" in result.prompt


def test_ssh_without_a_key_is_denied(shell):
    result = shell.execute("ssh root@10.11.7.42")
    assert result.output == "root@10.11.7.42: Permission denied (publickey)."


def test_ssh_to_the_wrong_address_times_out(shell):
    result = shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.99")
    assert result.output == "ssh: connect to host 10.11.7.99 port 22: Connection timed out"


def test_apt_update_and_upgrade(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    shell.execute("apt update")
    assert shell.state.system["pkg_index_updated"] is True
    shell.execute("apt upgrade")
    assert shell.state.system["pkg_upgraded"] is True


def test_apt_upgrade_before_update_does_not_satisfy_the_step(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    result = shell.execute("apt upgrade")
    assert result.output == "0 upgraded, 0 newly installed, 0 to remove"
    assert shell.state.system["pkg_upgraded"] is False


def test_apt_upgrade_without_yes_prompts_for_confirmation(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    shell.execute("apt update")
    result = shell.execute("apt upgrade")
    assert result.prompt is not None
    assert "Do you want to continue?" in result.prompt
    shell.answer("y")
    assert shell.state.system["pkg_upgraded"] is True


def test_adduser_and_usermod_and_key_copy(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    shell.execute("adduser maze-admin")
    shell.answer("secret")
    shell.answer("secret")
    shell.answer("")
    assert shell.state.system["users"]["maze-admin"]["sudo"] is False

    shell.execute("usermod -aG sudo maze-admin")
    assert shell.state.system["users"]["maze-admin"]["sudo"] is True

    shell.execute("rsync --archive --chown=maze-admin:maze-admin ~/.ssh /home/maze-admin")
    assert shell.state.system["users"]["maze-admin"]["has_ssh_key"] is True
    assert shell.state.system["admin_user"] == "maze-admin"


def test_usermod_without_a_flag_warns(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    shell.execute("adduser maze-admin")
    shell.answer("secret")
    shell.answer("secret")
    shell.answer("")
    result = shell.execute("usermod -G sudo maze-admin")
    assert "usermod" in result.output
    assert shell.state.system["users"]["maze-admin"]["sudo"] is False


def test_systemctl_reload_sshd_requires_valid_syntax(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]["syntax_valid"] = False
    result = shell.execute("systemctl reload sshd")
    assert result.output == "Job for ssh.service failed because the control process exited with error code."


def test_ssh_lockout_blocks_a_later_connection(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )
    shell.execute("systemctl reload sshd")
    shell.execute("exit")
    result = shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    assert "Permission denied" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: FAIL — `ServerShell` has no `answer` method / the new commands are unknown.

- [ ] **Step 3: Implement the commands in `src/utils/shell.py`**

Add to `ServerShell`:

- `_cmd_ssh(args)` — parse `[-i key] [-p port] user@host`. No `@` → `"ssh: no hostname given"`. The host must equal `10.11.7.42`; otherwise `"ssh: connect to host <host> port 22: Connection timed out"`. A `-i` key is required; without it, or when the key path is not in the filesystem, the result is `"<user>@<host>: Permission denied (publickey)."`. When the host is not yet in `state.system["known_hosts"]`, set `state.session["pending_prompt"] = {"kind": "ssh_host_key", "host": host, "user": user, "key": key}` and return `ShellResult(prompt=...)` with the spec's text:

  ```
  The authenticity of host '10.11.7.42 (10.11.7.42)' can't be established.
  ED25519 key fingerprint is SHA256:x7k9LmP2qR8vN1wZ4yB6cF0jH3dG5sA8tE9uI2oP4lM.
  Are you sure you want to continue connecting (yes/no/[fingerprint])?
  ```

  `answer()` for kind `"ssh_host_key"`: `"yes"` (case-insensitive) appends the host to `known_hosts`, sets `session["connected_via_ssh"] = True`, `machine = "maze-server"`, `user = "root"`, `cwd = "/root"`, `prompt_symbol = "#"`, and returns an empty `ShellResult`. `"no"` returns `ShellResult(output="Connection to 10.11.7.42 closed.")`. Anything else re-prompts with `"Please type 'yes', 'no' or the fingerprint: "`.

- `exit` on the server returns to the local workstation: `machine = "thuas-workstation"`, `user = "player"`, `cwd = "/home/player"`, `prompt_symbol = "$"`, `connected_via_ssh = False`. `exit` on the local workstation returns `ShellResult(exit_requested=True)`.

- `_cmd_apt(args)` — `apt` and `apt-get` are the same. Subcommands:
  - `update` → `state.system["pkg_index_updated"] = True`; output `"Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease"`.
  - `upgrade` → when `pkg_index_updated` is `False`, output `"0 upgraded, 0 newly installed, 0 to remove"` and do not set `pkg_upgraded`. Otherwise, if `-y` is present, set `pkg_upgraded = True`; if not, set `pending_prompt = {"kind": "apt_confirm"}` and return `ShellResult(prompt="Do you want to continue? [Y/n] ")`. The `apt_confirm` answer accepts `y`, `Y`, `yes`, or empty → `pkg_upgraded = True`; anything else → `"Abort."` and `pkg_upgraded` stays `False`.
  - `install <pkg>` → sets `state.system["services"]["nginx"]["installed"] = True` when the package is `nginx`; any other package → `"E: Unable to locate package <pkg>"`. Output `"Setting up nginx (1.18.0-6ubuntu14.3) ..."`.

- `_cmd_adduser(args)` — one username argument; more → `"adduser: Only one or two names allowed."`. Creates `state.system["users"][name] = {"sudo": False, "has_ssh_key": False}` and `state.system["admin_user"] = name` when `admin_user` is `None`. Sets `pending_prompt = {"kind": "adduser_password"}` and prompts `"New password: "`. The `adduser_password` answer flow asks `"Retype new password: "` then `"Is the information correct? [Y/n] "`; the password itself is not stored or checked for strength, but a mismatched retype re-asks. Any non-empty confirmation (`y`, `Y`, `yes`, or empty) accepts. An empty first password re-asks `"New password: "`.

- `_cmd_usermod(args)` — accepts `-aG <group> <user>` and `-a -G <group> <user>`. With `-aG`/`-a -G`, the user's `sudo` becomes `True` when the group is `sudo`. Without `-a`, output `"usermod: warning 'G' group memberships overwritten; use -a to append"` and the user's `sudo` stays unchanged. Unknown user → `"usermod: user 'x' does not exist"`.

- `_cmd_rsync(args)` — `--archive --chown=<user>:<group> <src> <dest>` copies the source directory's contents into the destination. Only `~/.ssh` → `/home/<user>` is supported; anything else → `"rsync: unsupported path"`. After copying, set `state.system["users"][<user>]["has_ssh_key"] = True` when the destination is `/home/<user>` and the source is `~/.ssh`. Also accept the alternative sequence from the spec: `mkdir -p /home/<user>/.ssh`, `cp ~/.ssh/authorized_keys /home/<user>/.ssh/`, and `chown -R <user>:<user> /home/<user>/.ssh` — implement `mkdir`, `cp`, and `chown` commands too, and set `has_ssh_key` when `authorized_keys` ends up in the target user's `.ssh` directory with the right owner.

- `_cmd_systemctl(args)` — `enable`, `start`, `restart`, `reload`, `status`, each optionally with `--now`. For `sshd`: `enable` sets `services["sshd"]["enabled"] = True`, `start`/`restart`/`reload` sets `services["sshd"]["running"] = True`. A `reload`/`restart` when the sshd config's `syntax_valid` is `False` returns `"Job for ssh.service failed because the control process exited with error code."` and changes nothing. For `nginx`: `enable` sets `services["nginx"]["enabled"] = True`, `start`/`restart`/`reload` sets `services["nginx"]["running"] = True`; a start/reload while the nginx site config's `syntax_valid` is `False` returns `"Job for nginx.service failed because the control process exited with error code."`. `status nginx` sets `health_verified["service_status_checked"] = True` when nginx is running and outputs the spec's `Active: active (running)` block. Unknown service → `"System has not been booted with systemd."`.

- `_cmd_sshd(args)` — the `sshd -t` syntax check. The dispatcher looks up `_cmd_<first token>`, so the command name is `sshd` and the flag is the argument. It validates `/etc/ssh/sshd_config`; when `syntax_valid` is `True` returns an empty `ShellResult`, otherwise `"sshd: /etc/ssh/sshd_config: line 3: Bad configuration option"`.

- `_cmd_su(args)` — `su - <user>` switches to that user: `state.session["user"]` becomes the named user, `cwd` becomes that user's home (`/home/<user>`, or `/root` for root), and `prompt_symbol` becomes `"$"` for a non-root user and `"#"` for root. Switching to a user that does not exist in `state.system["users"]` returns `"su: user '<name>' does not exist"`. `su` with no argument returns to `root`.

- Command aliases: `_cmd_apt_get = _cmd_apt`, `_cmd_vim = _cmd_nano`, `_cmd_netstat = _cmd_ss`.

- SSH lockout: when an `ssh` attempt is made and `services["sshd"]` has `PermitRootLogin == "no"` and `PasswordAuthentication == "no"` and no user has `has_ssh_key` `True`, the attempt returns `"root@10.11.7.42: Permission denied (publickey)."`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/shell.py tests/test_server_shell.py
git commit -m "feat(shell): add ssh, user, package and service commands to ServerShell"
```

---

### Task 7: `ServerShell` — firewall, network, time, web stack, verification

**Files:**
- Modify: `src/utils/shell.py` — add commands to `ServerShell`
- Modify: `tests/test_server_shell.py`

**Interfaces:**
- Consumes: `ServerShell` (Task 6)
- Produces: additional `ServerShell` commands

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server_shell.py`:

```python
def _connected_shell(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    return shell


def test_ufw_default_policies_and_allow_rules(shell):
    _connected_shell(shell)
    shell.execute("ufw default deny incoming")
    assert shell.state.system["firewall"]["default_incoming"] == "deny"
    shell.execute("ufw default allow outgoing")
    assert shell.state.system["firewall"]["default_outgoing"] == "allow"
    shell.execute("ufw allow 22/tcp")
    shell.execute("ufw allow 80/tcp")
    shell.execute("ufw allow 443/tcp")
    assert set(shell.state.system["firewall"]["allowed_ports"]) == {22, 80, 443}


def test_ufw_enable_prompts_for_confirmation(shell):
    _connected_shell(shell)
    result = shell.execute("ufw enable")
    assert result.prompt is not None
    assert "Command may disrupt existing ssh connections" in result.prompt
    assert shell.state.system["firewall"]["active"] is False


def test_ufw_enable_without_the_ssh_port_severs_the_session(shell):
    _connected_shell(shell)
    shell.execute("ufw default deny incoming")
    shell.execute("ufw enable")
    result = shell.answer("y")
    assert "Broken pipe" in result.output
    assert shell.state.session["machine"] == "thuas-workstation"
    assert shell.state.system["firewall"]["active"] is False
    assert shell.state.system["firewall"]["default_incoming"] == "allow"


def test_ufw_enable_with_the_ssh_port_succeeds(shell):
    _connected_shell(shell)
    shell.execute("ufw default deny incoming")
    shell.execute("ufw allow 22/tcp")
    shell.execute("ufw enable")
    shell.answer("y")
    assert shell.state.system["firewall"]["active"] is True
    assert shell.state.session["machine"] == "maze-server"


def test_hostnamectl_and_hosts_mapping(shell):
    _connected_shell(shell)
    shell.execute("hostnamectl set-hostname maze-server.thuas.nl")
    assert shell.state.system["hostname"] == "maze-server.thuas.nl"
    shell.state.filesystem["/etc/hosts"]["content"] = (
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server.thuas.nl maze-server\n"
    )
    shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server.thuas.nl maze-server\n",
    )
    assert shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is True


def test_netplan_apply_requires_valid_yaml(shell):
    _connected_shell(shell)
    shell.state.set_file_content(
        "/etc/netplan/50-cloud-init.yaml",
        "network:\n  version: 2\n  ethernets:\n   eth0:\n      dhcp4: true\n",
    )
    result = shell.execute("netplan apply")
    assert result.output == (
        "/etc/netplan/50-cloud-init.yaml:5:7: Error in network definition: invalid YAML"
    )


def test_timedatectl_sets_ntp(shell):
    _connected_shell(shell)
    shell.execute("timedatectl set-timezone UTC")
    assert shell.state.system["timezone"] == "Etc/UTC"
    shell.execute("timedatectl set-ntp true")
    assert shell.state.system["ntp_synced"] is True


def test_timedatectl_status_shows_the_clock(shell):
    _connected_shell(shell)
    output = shell.execute("timedatectl status").output
    assert "System clock synchronized: no" in output


def test_nginx_install_configure_and_enable(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt install nginx")
    assert shell.state.system["services"]["nginx"]["installed"] is True

    shell.execute("mkdir -p /etc/nginx/sites-available")
    shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    shell.execute("ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app")
    assert shell.state.filesystem["/etc/nginx/sites-enabled/app"]["type"] == "link"
    assert shell.state.filesystem["/etc/nginx/sites-available/app"]["parsed"]["enabled"] is True

    result = shell.execute("nginx -t")
    assert result.output == "nginx: the configuration file /etc/nginx/nginx.conf syntax is ok"


def test_nginx_t_reports_a_broken_block(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt install nginx")
    shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze\n",
    )
    result = shell.execute("nginx -t")
    assert "nginx: [emerg] unexpected" in result.output
    assert "test failed" in result.output


def test_mkdir_chown_chmod_set_permissions(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt install nginx")
    shell.execute("mkdir -p /var/www/maze")
    shell.execute("chown -R maze-admin:www-data /var/www/maze")
    shell.execute("chmod -R 755 /var/www/maze")
    node = shell.state.filesystem["/var/www/maze"]
    assert node["owner"] == "maze-admin:www-data"
    assert node["perms"] == "755"


def test_systemctl_enable_now_starts_nginx(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt install nginx")
    shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    shell.execute("ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app")
    shell.execute("systemctl enable --now nginx")
    assert shell.state.system["services"]["nginx"]["enabled"] is True
    assert shell.state.system["services"]["nginx"]["running"] is True


def test_verification_commands_set_the_health_flags(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt install nginx")
    shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    shell.execute("ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app")
    shell.execute("systemctl enable --now nginx")

    shell.execute("systemctl status nginx")
    assert shell.state.system["health_verified"]["service_status_checked"] is True

    shell.execute("ss -tulpn")
    assert shell.state.system["health_verified"]["ports_checked"] is True

    shell.execute("curl -I http://localhost")
    assert shell.state.system["health_verified"]["logs_or_http_checked"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: FAIL — the new commands are unknown.

- [ ] **Step 3: Implement the commands in `src/utils/shell.py`**

Add to `ServerShell`:

- `_cmd_ufw(args)` — `default deny incoming` / `default allow outgoing` set `state.system["firewall"]["default_incoming"]` / `["default_outgoing"]`. `allow <port>/tcp` adds the integer port to `allowed_ports`; `allow OpenSSH` adds `22`; `allow 'Nginx Full'` adds `80` and `443`. `enable` sets `pending_prompt = {"kind": "ufw_confirm"}` and prompts `"Command may disrupt existing ssh connections. Proceed with operation (y|n)? "`. The `ufw_confirm` answer: `y` or `yes` activates the firewall — **but only when the sshd port is in `allowed_ports`**; otherwise the session is severed: output `"client_loop: send disconnect: Broken pipe"`, `firewall["active"] = False`, `default_incoming` and `default_outgoing` revert to `"allow"`, `allowed_ports` keeps the rules the player entered, `session["machine"]` reverts to `"thuas-workstation"`, `user` to `"player"`, `cwd` to `"/home/player"`, `prompt_symbol` to `"$"`, `connected_via_ssh` to `False`. Any other answer → `"Command cancelled"`.

- `_cmd_hostnamectl(args)` — `set-hostname <fqdn>` sets `state.system["hostname"]` and `state.session["machine"]` to the first label of the FQDN (`maze-server`). A hostname without a dot is accepted as-is.

- `_cmd_netplan(args)` — `apply` and `try`. When the netplan file's `parsed["syntax_valid"]` is `False`, output the spec's `/etc/netplan/50-cloud-init.yaml:5:7: Error in network definition: invalid YAML`. Otherwise apply the static IP: set `state.system["ip_address"]` to the address in the file, `state.session["machine"]` to the hostname.

- `_cmd_timedatectl(args)` — `set-timezone <tz>` sets `state.system["timezone"]` (accepting any non-empty value; `UTC` is stored as `Etc/UTC`). `set-ntp true|on` sets `state.system["ntp_synced"] = True`. `status` prints the spec's `timedatectl status` block, with `System clock synchronized: yes` when `ntp_synced` is `True` and `no` otherwise, and `NTP service: active` when synced.

- `_cmd_mkdir(args)` — accepts `-p`. Creates a directory node at the path (and any missing parents) with `perms "755"` and `owner` taken from the session user.

- `_cmd_chown(args)` — `chown -R <user>:<group> <path>` sets the node's `owner`; `chown <user> <path>` sets `owner` to `<user>:<group>` where the group is the user's group. Unknown path → `"chown: cannot access '<path>': No such file or directory"`. With `-R`, apply to the path and every descendant.

- `_cmd_chmod(args)` — `chmod -R <mode> <path>` sets the node's `perms`; the mode is one of `"755"` or `"750"`; other modes are accepted but stored verbatim. Unknown path → `"chmod: cannot access '<path>': No such file or directory"`. With `-R`, apply to the path and every descendant.

- `_cmd_cp(args)` — `cp <src> <dest>` copies a file node's content to the destination path, creating the destination when needed.

- `_cmd_ln(args)` — `ln -s <target> <link>` creates a link node `{"type": "link", "target": <target>}` at the link path. Set `parsed["enabled"] = True` on `/etc/nginx/sites-available/app` when the link path is `/etc/nginx/sites-enabled/app` and the target is that file.

- `_cmd_nginx(args)` — `-t` validates the site config: when `/etc/nginx/sites-available/app` is missing → `"nginx: [emerg] no host configuration found"`; when its `parsed["syntax_valid"]` is `False` → the spec's two-line error (`nginx: [emerg] unexpected "}" in /etc/nginx/sites-enabled/app:12` and `nginx: configuration file /etc/nginx/nginx.conf test failed`); otherwise `"nginx: the configuration file /etc/nginx/nginx.conf syntax is ok"`.

- `_cmd_ss(args)` / `_cmd_netstat(args)` — list the listening sockets: sshd on `state.system["services"]["sshd"]["port"]` and nginx on `80` when installed. Output lists `sshd` and `nginx` lines. Set `health_verified["ports_checked"] = True`.

- `_cmd_curl(args)` — `-I <url>` where the url is `http://localhost` returns `"HTTP/1.1 200 OK"` when nginx is running and the `/var/www/maze` permissions are `755`/`750`; when the permissions are `700` it returns `"HTTP/1.1 403 Forbidden"`. Set `health_verified["logs_or_http_checked"] = True`.

- `_cmd_tail(args)` — `tail -n <count> <file>` prints the last lines of the file; for `/var/log/nginx/access.log` it appends a `GET / 200` line on the first call and sets `health_verified["logs_or_http_checked"] = True`.

- `_cmd_journalctl(args)` — `-u nginx` prints a short journal summary; sets `health_verified["logs_or_http_checked"] = True`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/shell.py tests/test_server_shell.py
git commit -m "feat(shell): add firewall, network, web and verification commands"
```

---

### Task 8: `checklist` command and the completion screen

**Files:**
- Modify: `src/utils/shell.py` — add `_cmd_checklist`
- Modify: `tests/test_server_shell.py`

**Interfaces:**
- Consumes: `ServerState.steps()` from Task 1
- Produces: `ServerShell._cmd_checklist(args) -> ShellResult`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server_shell.py`:

```python
def test_checklist_lists_all_eleven_steps_with_progress(shell):
    _connected_shell(shell)
    output = shell.execute("checklist").output
    assert output.count("\n") == 11
    assert "[x]" not in output
    assert "[ ]" in output
    assert "Step 1" in output
    assert "ssh -i ~/.ssh/id_ed25519 root@10.11.7.42" in output


def test_checklist_marks_completed_steps(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt upgrade")
    output = shell.execute("checklist").output
    assert "[x]" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: FAIL — `bash: checklist: command not found`

- [ ] **Step 3: Implement `_cmd_checklist` in `src/utils/shell.py`**

```python
    def _cmd_checklist(self, args: list[str]) -> ShellResult:
        """Print the 11 provisioning steps and their completion state."""
        lines = []
        for number, step in enumerate(self.state.steps(), start=1):
            mark = "[x]" if step.done else "[ ]"
            lines.append(f"{mark} Step {number} — {step.title}")
            if not step.done and step.hint:
                lines.append(f"      {step.hint}")
        return ShellResult(output="\n".join(lines))
```

The hint text for the `ssh` step must contain `ssh -i ~/.ssh/id_ed25519 root@10.11.7.42` so the player is not left guessing.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server_shell.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/shell.py tests/test_server_shell.py
git commit -m "feat(shell): add checklist command showing provisioning progress"
```

---

### Task 9: `LabD2001.inspect_server` — run the terminal session

**Files:**
- Modify: `src/rooms/lab_d2_001.py`
- Modify: `tests/test_engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `ServerShell` (Task 8), `State.server` (Task 2)
- Produces: `LabD2001.inspect_server() -> None` — the room's terminal entry point, already dispatched from `Engine.inspect` for target `"server"` in room `lab_d2_001`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_engine.py`:

```python
def test_inspect_server_runs_the_terminal_session(oop_engine, monkeypatch):
    oop_engine.player["current_room"] = "lab_d2_001"
    oop_engine.session["duration"]["value"] = "0:05:00"
    monkeypatch.setattr("src.rooms.lab_d2_001.loader", lambda **kwargs: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "exit")

    oop_engine.inspect_server()

    # The terminal session is not charged to the player, and the clock resumes.
    assert oop_engine.session["duration"]["value"] == "0:05:00"
    assert oop_engine.session["duration"]["pause"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine.py::test_inspect_server_runs_the_terminal_session -q --no-cov`
Expected: FAIL — `inspect_server` currently only prints a prompt.

- [ ] **Step 3: Implement `inspect_server` in `src/rooms/lab_d2_001.py`**

Replace the current body with a terminal session:

```python
    def inspect_server(self) -> None:
        """Open the lab workstation terminal and run the provisioning challenge.

        Pauses the game clock for the whole session and rebases it on exit, so
        terminal time is never charged to the player.
        """
        loader(
            loading_time=1.2,
            label="Booting up workstation...",
            mode="LOADER",
        )
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
            # ``auto()`` rebases ``last_write`` while the clock is still paused, so
            # the time spent in the terminal is discarded rather than charged.
            self.auto()
            self.session["duration"]["pause"] = False
            self.clear()
            self.render()
```

Add the import `from src.utils.shell import ServerShell`.

Note the ordering: `self.auto()` runs while the clock is still paused (so it advances
`last_write` but does not add elapsed time to `duration["value"]`), then the clock is
unpaused and the room is re-rendered. This mirrors `teachers_room_4.py::inspect_computer`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_engine.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/rooms/lab_d2_001.py tests/test_engine.py
git commit -m "feat(lab): run the server provisioning terminal in lab_d2_001"
```

---

### Task 10: Completion — flag, item award, and the activation gate

**Files:**
- Modify: `src/rooms/lab_d2_001.py` — award on completion
- Modify: `src/rooms/lab_d2_002.py` — `activate()` gate
- Modify: `tests/test_engine.py`

**Interfaces:**
- Consumes: `ServerState.complete` (Task 1), `State.server` (Task 2)
- Produces: `LabD2001._award_provisioning_certificate() -> None`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_engine.py`:

```python
def test_completing_the_challenge_sets_the_flag_and_awards_the_item(oop_engine, monkeypatch):
    oop_engine.player["current_room"] = "lab_d2_001"
    oop_engine.server.system["pkg_index_updated"] = True
    oop_engine.server.system["pkg_upgraded"] = True
    monkeypatch.setattr("src.rooms.lab_d2_001.loader", lambda **kwargs: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "exit")

    oop_engine.inspect_server()

    assert oop_engine.flags["lab_server_provisioned"] is True
    assert "server_provisioning_certificate" in oop_engine.player["inventory"]


def test_activate_refuses_until_the_server_is_provisioned(oop_engine, monkeypatch):
    oop_engine.player["current_room"] = "lab_d2_002"
    oop_engine.workbench["installed_parts"] = list(oop_engine.workbench["required_parts"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "Tr0janH0rse!")

    oop_engine.activate()

    assert oop_engine.session["phase"] == "EXPLORATION"
    assert any("provisioned" in line for line in oop_engine.outputs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine.py -q --no-cov`
Expected: FAIL — the flag is never set and `activate()` does not gate.

- [ ] **Step 3: Implement the award and the gate**

In `src/rooms/lab_d2_001.py`:

```python
    def _award_provisioning_certificate(self) -> None:
        """Mark the challenge complete and grant the certificate once."""
        self.flags["lab_server_provisioned"] = True
        if "server_provisioning_certificate" in self.player["inventory"]:
            return
        self.player["inventory"].append("server_provisioning_certificate")
        name = self.items["server_provisioning_certificate"]["name"]
        self.out(self.colorize(text=f"{name} added to your inventory!", color_code=self.color.SUCCESS))
```

Call it at the end of `inspect_server`, after the session loop, only when `self.state.server.complete` is `True`:

```python
        if self.state.server.complete:
            self._award_provisioning_certificate()
            self.out(
                self.colorize(
                    text="Server Provisioning Complete — the robot's neural link can come up.",
                    color_code=self.color.SUCCESS,
                )
            )
```

In `src/rooms/lab_d2_002.py`, add at the very start of `activate()`, before the missing-parts check:

```python
        if not self.flags.get("lab_server_provisioned"):
            self.render_workbench(
                text=self.colorize(
                    text="The robot's neural link needs the maze-server backend provisioned first. "
                         "Finish the server configuration in Lab D 2001.",
                    color_code=self.color.ERROR,
                )
            )
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_engine.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/rooms/lab_d2_001.py src/rooms/lab_d2_002.py tests/test_engine.py
git commit -m "feat(lab): award the provisioning certificate and gate activation on it"
```

---

### Task 11: Documentation and full verification

**Files:**
- Modify: `docs/STATE_SCHEMA.md`
- Modify: `docs/COMMAND_REFERENCE.md`

**Interfaces:**
- Consumes: everything above.
- Produces: documentation only.

- [ ] **Step 1: Update `docs/STATE_SCHEMA.md`**

Add a `server` section to the root-structure description and the template, documenting:

- `server.session` — `machine`, `user`, `cwd`, `prompt_symbol`, `connected_via_ssh`, `pending_prompt`
- `server.filesystem` — a flat path→node map; file nodes carry `type`, `content`, `perms`, `owner`, `parsed`; directory nodes carry `type`, `perms`, `owner`; link nodes carry `type`, `target`
- `server.system` — `ip_address`, `known_hosts`, `pkg_index_updated`, `pkg_upgraded`, `users`, `hostname`, `timezone`, `ntp_synced`, `admin_user`, `firewall`, `services`, `health_verified`
- the `lab_server_provisioned` flag row in the flags table
- the `server_provisioning_certificate` item
- a note that `required_parts` is derived from the `is_assembly_part` flag, and that `server` is persisted via `_PERSIST_KEYS`

- [ ] **Step 2: Update `docs/COMMAND_REFERENCE.md`**

Document the server shell: the two machines, the `sudo` prefix, the interactive sub-prompts, and the full command list grouped as in the design doc §4.5.

- [ ] **Step 3: Run the full verification suite**

Run:
```bash
python -m pytest -q
ruff check .
mypy .
```
Expected: all tests pass, coverage ≥ 80%, ruff reports "All checks passed!", mypy reports "Success: no issues found".

- [ ] **Step 4: Confirm the challenge is completable end to end**

Run a scripted session through `ServerShell` covering all 11 steps in a non-interactive harness (drive `execute`/`answer` directly with a helper that answers each pending prompt), and assert `state.server.complete` is `True` and `flags["lab_server_provisioned"]` is `True`.

- [ ] **Step 5: Commit**

```bash
git add docs/STATE_SCHEMA.md docs/COMMAND_REFERENCE.md
git commit -m "docs: document the server provisioning challenge state and commands"
```
