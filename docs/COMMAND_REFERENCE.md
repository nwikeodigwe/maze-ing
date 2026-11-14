# A-maze-ing-Delft - Command Reference Manual

This manual lists all supported commands, shortcuts, directional aliases, and phase-specific mechanics in A-maze-ing-Delft.

## 1. Input Processing Rules

The engine normalizes all user input before passing it to `src/parser.py`:

- **Case-Insensitive:** `GO <ROOM>`, `Go <Room>`, and `go <north>` are treated identically.
- **Trimmed Whitespace:** Leading, trailing, and duplicate spaces are stripped (`take   battery_pack` → `take battery_pack`).
- **Noise Word Stripping:** Articles like `the`, `a`, and `an` are ignored (`take the battery_pack` → `take battery_pack`).

## 2. Exploration Phase Commands

During EXPLORATION mode, player commands follow a `VERB [TARGET]` or `VERB [ITEM] ON [TARGET]` pattern.

### Spatial Movement

| Command Syntax | Aliases / Shortcuts          | Example              | Target Action / Result                            |
| -------------- | ---------------------------- | -------------------- | ------------------------------------------------- |
| `go [room]`    | `move [room]`, `walk [room]` | `go teachers_room_1` | Moves player to the destination room if unlocked. |

### Environment & Inspection

| Command Syntax     | Aliases / Shortcuts                                   | Example                                | Target Action / Result                                              |
| ------------------ | ----------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------- |
| `look`             | `l`, `ls`, `examine room`                             | `look`                                 | Displays current room title, description, visible items, and exits. |
| `inspect [target]` | `examine [target]`, `read [target]`, `check [target]` | `inspect desk`, `inspect battery_pack` | Inspects a room object or item.                                     |

### Inventory Management

| Command Syntax | Aliases / Shortcuts                           | Example             | Target Action / Result                                                    |
| -------------- | --------------------------------------------- | ------------------- | ------------------------------------------------------------------------- |
| `inventory`    | `inv`, `i`                                    | `inventory`         | Lists all items currently held in player inventory.                       |
| `take [item]`  | `get [item]`, `grab [item]`, `pick up [item]` | `take battery_pack` | Transfers an item from the current room floor into player inventory.      |
| `drop [item]`  | `discard [item]`                              | `drop battery_pack` | Transfers an item from player inventory back onto the current room floor. |

### Interactions & Puzzles

| Command Syntax           | Aliases / Shortcuts                                  | Example                    | Target Action / Result                                                   |
| ------------------------ | ---------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------ |
| `use [item]`             | `apply [item]`                                       | `use keycard_lvl1`         | Uses an item in the current context (e.g., swiping a keycard at a door). |
| `use [item] on [target]` | `apply [item] to [target]`, `put [item] on [target]` | `use keycard_lvl1 on door` | Direct interaction between an inventory item and a room interactable.    |
| `enter [code]`           | `type [code]`, `unlock [code]`                       | `enter 2015`               | Submits a keypad code to an interactable.                                |

### System & Meta Commands

| Command Syntax | Aliases / Shortcuts | Example | Target Action / Result                                              |
| -------------- | ------------------- | ------- | ------------------------------------------------------------------- |
| `save`         | `save game`         | `save`  | Writes current in-memory state to `saves/save_slot_1.json`.         |
| `load`         | `load game`         | `load`  | Restores game state from `saves/save_slot_1.json`.                  |
| `help`         | `?`, `commands`     | `help`  | Renders a quick summary of command verbs inside the CLI.            |
| `quit`         | `exit`, `q`         | `quit`  | Prompts for save verification, then cleanly terminates application. |

## 3. Server Provisioning Shell (Lab D 2001)

Inspecting the **server** in `lab_d2_001` opens a shell session. The player starts on the
workstation (`player@thuas-workstation:~$`) and reaches the server over SSH. Progress is
persisted with the game, so the challenge can be left and resumed.

| Command Syntax              | Aliases / Shortcuts            | Example                                | Target Action / Result                                                       |
| --------------------------- | ------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------- |
| `ssh [-i key] [-p port] user@host` | —                        | `ssh -i ~/.ssh/id_ed25519 root@10.11.7.42` | Connects to the server; asks to confirm the host key the first time. |
| `sudo <command>`            | —                               | `sudo apt update`                      | Runs a command as root; refuses if the user has no sudo rights.               |
| `su - <user>`               | `su <user>`                     | `su - maze-admin`                      | Switches to another account.                                                 |
| `whoami` / `groups`         | —                               | `whoami`                               | Prints the current user and its groups.                                      |
| `apt update` / `apt upgrade` | `apt-get ...`                 | `apt update && apt upgrade -y`         | Refreshes the package index and applies upgrades; asks to confirm without `-y`. |
| `apt install <package>`     | `apt-get install <package>`     | `apt install nginx`                    | Installs a package.                                                           |
| `adduser <name>`            | —                               | `adduser maze-admin`                   | Creates an account; prompts for the password.                                 |
| `usermod -aG sudo <name>`   | —                               | `usermod -aG sudo maze-admin`          | Gives the account sudo rights; warns without `-a`.                             |
| `rsync --archive --chown=u:g ~/.ssh /home/<u>` | `cp`/`mkdir`/`chown` equivalents | `rsync --archive --chown=maze-admin:maze-admin ~/.ssh /home/maze-admin` | Copies the SSH keys to the new account. |
| `nano <file>` / `vim <file>` | `sed -i 's/old/new/' <file>`     | `nano /etc/ssh/sshd_config`            | Opens the file in the modal editor; saving re-parses the configuration.       |
| `sshd -t`                   | —                               | `sshd -t`                              | Validates the SSH configuration.                                             |
| `systemctl enable\|start\|reload\|status <unit>` | `service ...`        | `systemctl enable --now nginx`         | Manages a service; refuses when the configuration is invalid.                 |
| `ufw default allow\|deny incoming\|outgoing` | —          | `ufw default deny incoming`           | Sets the firewall policy.                                                    |
| `ufw allow <port>/tcp`      | `ufw allow OpenSSH`, `ufw allow 'Nginx Full'` | `ufw allow 22/tcp`  | Opens a port; the SSH port must be allowed before `ufw enable`.                |
| `ufw enable`                | —                               | `ufw enable`                           | Activates the firewall; asks to confirm, and severs the session if the SSH port is not allowed. |
| `hostnamectl set-hostname <name>` | —                        | `hostnamectl set-hostname maze-server.thuas.nl` | Sets the server hostname.                                            |
| `netplan apply`             | `netplan try`                   | `netplan apply`                        | Applies the network configuration; refuses on invalid YAML.                   |
| `timedatectl set-timezone <tz>` / `set-ntp true` | `timedatectl status` | `timedatectl set-ntp true`   | Sets the timezone and enables NTP synchronisation.                           |
| `nginx -t`                  | —                               | `nginx -t`                             | Validates the nginx configuration.                                          |
| `mkdir -p <path>`           | `mkdir`                          | `mkdir -p /var/www/maze`               | Creates a directory.                                                         |
| `chown -R <user>:<group> <path>` | `chown`                     | `chown -R maze-admin:www-data /var/www/maze` | Sets ownership.                                                       |
| `chmod -R <mode> <path>`    | `chmod`                          | `chmod -R 755 /var/www/maze`           | Sets permissions.                                                            |
| `ln -s <target> <link>`     | `ln`                             | `ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app` | Enables the site.          |
| `ss -tulpn`                 | `netstat -tulpn`                 | `ss -tulpn`                            | Lists the listening sockets.                                                 |
| `curl -I <url>`             | `tail -n 20 <log>`, `journalctl -u <unit>` | `curl -I http://localhost`   | Checks the service over HTTP or in its logs.                                  |
| `checklist`                 | —                               | `checklist`                            | Shows the eleven provisioning steps and how many are done.                     |
| `help [<name>]`             | `help ssh`, `help ufw`           | `help ufw`                             | Summarises the mission and every command group; with a name, shows one command's usage. |
| `ls`, `cd`, `pwd`, `cat`    | `ls -a`, `ls -l`                 | `cat /etc/ssh/sshd_config`             | Browse and read the server filesystem.                                       |
| `exit`                      | —                               | `exit`                                 | Leaves the server, or the terminal when already on the workstation.           |

The terminal's `help` opens with the mission ("Provision the maze-server..."),
your current machine and the next expected step, then a grouped command list
with `help <name>` for per-command usage. The room's own `inspect guide`
interactable reads `data/guides/lab_d2_001.txt`, a full walkthrough of the
eleven steps and the challenge's two traps.

The challenge is complete when all eleven steps pass; the game then sets
`lab_server_provisioned` and awards the *Server Provisioning Certificate*, which is
required before the robot can be activated.

## 4. Assembly Phase Commands

When all 7 required components are placed on the workbench in `lab_d2001`, `game_phase` transitions to `"ASSEMBLY"`.

| Command Syntax      | Aliases / Shortcuts         | Example             | Target Action / Result                                              |
| ------------------- | --------------------------- | ------------------- | ------------------------------------------------------------------- |
| `activate`          | `power on`, `start`, `boot` | `activate`          | Triggers boot sequence animation and transitions game to CHAT_MODE. |
| `inspect workbench` | `check workbench`           | `inspect workbench` | Displays list of installed hardware parts vs. missing components.   |
| `look`              | `l`, `ls`                   | `look`              | Re-renders terminal header and workbench state.                     |

> **Note:** Navigation (`go`) and item dropping are disabled while in the Assembly state until the unit is activated.

## 5. Phase 3 (AI Chat Mode) Mechanics

Once `activate` is executed, standard command verbs are bypassed. All user input is treated as freeform natural language.

### Input Handling Pipeline

```text
Player Input -> src/client.py -> OpenAI Chat Completions API -> Streaming Response
```

## 6. Parser Error & Feedback Matrix

| Scenario / Error Condition | Parser / Engine Output                                                          |
| -------------------------- | ------------------------------------------------------------------------------- |
| Unknown Command            | `I don't understand that command. Type 'help' for a list of available actions.` |
| Missing Target Parameter   | `What do you want to [verb]? (e.g., '[verb] battery_pack')`                     |
| Item Not in Room           | `There is no '[item]' here.`                                                    |
| Item Not in Inventory      | `You are not carrying '[item]'.`                                                |
| Target Door Locked         | `The door is locked. Access requires: Level-1 Staff Keycard.`                   |
| Invalid Direction          | `You cannot go [direction] from here.`                                          |
| Incorrect Keypad Code      | `Keypad buzzes red: Incorrect code entered.`                                    |
