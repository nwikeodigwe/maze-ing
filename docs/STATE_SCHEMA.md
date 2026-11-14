# A-maze-ing-Delft - Game State Schema Specification

This document defines the data structure, schema definitions, validation rules, and default JSON representation for the `game_state` object in A-maze-ing-Delft.

## 1. Schema Overview & Data Integrity Rules

The `game_state` object is the single source of truth for the game runtime. It tracks game progression, world topology, item ownership, and assembly triggers across three distinct execution phases.

### Data Integrity Rules

- **Strict JSON Serialization:** Only primitive types (`string`, `number`, `boolean`), arrays (`list`), and key-value objects (`dict`) are permitted. Custom class instances, function pointers, or lambda expressions are strictly forbidden.
- **Canonical Identifiers:** All lookups for rooms, items, and flags must use canonical snake_case keys (e.g., `teachers_room_1`, `red_led`). Never use human-readable display names in conditional logic or state lookups.
- **Template Immutability:** `../data/default.json` serves as the read-only initial world state. Runtime mutations must occur solely on the in-memory state dictionary and be saved to `saves/save_slot_1.json`.

## 2. Root Structure & Key Specifications

The root object contains `running`, `enable_colors`, `terminal_width`, `player`, `workbench`, `flags`, `rooms`, `items`, `server`, and `session`. The phase lives under `session["phase"]`, not at the root. See detailed definitions below and the full template in Section 4.

The `workbench.required_parts` list is **derived**, not authored: on every load the state fills it with the ids of every item whose `is_assembly_part` flag is true, so the parts the player must install always match the item data.

### Server Challenge State (`server`)

The Lab D 2001 provisioning challenge. It is persisted with the rest of the game, so a player can leave the lab and resume exactly where they were.

```json
"server": {
    "session": {
        "machine": "string",
        "user": "string",
        "cwd": "string",
        "prompt_symbol": "string",
        "connected_via_ssh": "boolean",
        "pending_prompt": null
    },
    "filesystem": {
        "/absolute/path": {
            "type": "file",
            "content": "string",
            "perms": "string",
            "owner": "string",
            "parsed": {}
        },
        "/absolute/path": { "type": "dir", "perms": "string", "owner": "string" }
    },
    "system": {
        "ip_address": "string",
        "known_hosts": ["string"],
        "pkg_index_updated": "boolean",
        "pkg_upgraded": "boolean",
        "admin_user": "string",
        "users": { "user": { "sudo": "boolean", "has_ssh_key": "boolean" } },
        "hostname": "string",
        "timezone": "string",
        "ntp_synced": "boolean",
        "firewall": {
            "active": "boolean",
            "default_incoming": "string",
            "default_outgoing": "string",
            "allowed_ports": ["int"]
        },
        "services": {
            "sshd": { "installed": "boolean", "running": "boolean", "enabled": "boolean", "port": "int" },
            "nginx": { "installed": "boolean", "running": "boolean", "enabled": "boolean", "port": "int" }
        },
        "health_verified": {
            "service_status_checked": "boolean",
            "ports_checked": "boolean",
            "logs_or_http_checked": "boolean"
        }
    }
}
```

- `session.pending_prompt` is `null`, or the sub-prompt the shell is waiting on (`ssh_host_key`, `apt_confirm`, `ufw_confirm`, `adduser_password`).
- `filesystem` is a flat map keyed by absolute path. Config files store their text in `content`; the fields the game checks are derived from that text into `parsed` by a per-file parser.
- The challenge is complete when all eleven step predicates hold; the `checklist` command shows the player which are done.


## 3. Detailed Field Definitions

### Player State (`player`)

```json
"player": {
    "current_room": "string",
    "inventory": ["string"]
}
```

### Workbench Tracker (`workbench`)

```json
"workbench": {
    "installed_parts": ["string"],
    "required_parts": ["string"],
    "is_ready": "boolean"
}
```

### Story Flags (`flags`)

Dictionary of boolean keys used for tracking non-item progression events.

| Flag Key                   | Type    | Default | Trigger Condition / Meaning                                         |
| -------------------------- | ------- | ------- | ------------------------------------------------------------------- |
| `tr1_desk_unlocked`        | boolean | false   | true when the desk keypad code (2015) in teachers_room_1 is solved. |
| `tr2_whiteboard_inspected` | boolean | false   | true when inspect whiteboard is issued in teachers_room_2.          |
| `tr4_drawer_decrypted`     | boolean | false   | true when the desk in teachers_room_4 is searched/decrypted.        |
| `tr4_secret_key_copied`    | boolean | false   | true when the secret file in teachers_room_4 is read; key copied.   |
| `lab_power_on`             | boolean | false   | true when power is restored to the workbench terminal in lab_d2_002. |
| `lab_server_provisioned`   | boolean | false   | true when all eleven server provisioning steps are complete in lab_d2_001. |

### Item Entities (`items`)

```json
"items": {
    "item_id": {
        "name": "string",
        "description": "string",
        "is_assembly_part": "boolean"
    }
}
```

`server_provisioning_certificate` is awarded when the server challenge is finished. It is not an assembly part, so it never affects the robot build.

### Room Graph Entities (`rooms`)

Dictionary mapping unique room_id strings to room definition objects.

```json
"rooms": {
    "room_id": {
        "id": "string",
        "name": "string",
        "description": "string",
        "restricted": "boolean",
        "requires": ["string"],
        "exits": {
            "direction": "room_id"
        },
        "items": ["string"],
        "interactables": {
            "object_name": "string | object"
        }
    }
}
```

## 4. Master Template JSON (`../data/default.json`)

The authoritative template is `data/default.json` itself. The root object's shape is:

```json
{
  "running": true,
  "enable_colors": true,
  "terminal_width": 80,
  "player": { "current_room": "lobby", "inventory": [] },
  "workbench": { "installed_parts": [], "is_ready": false },
  "flags": { "tr1_desk_unlocked": false, "lab_server_provisioned": false, "...": false },
  "rooms": { "lobby": { "id": "lobby", "name": "Lobby", "restricted": false, "requires": [], "exits": {}, "items": [], "interactables": {} }, "...": {} },
  "items": { "item_id": { "name": "string", "description": "string", "is_assembly_part": false } },
  "server": { "session": {}, "filesystem": {}, "system": {} },
  "session": { "phase": "EXPLORATION", "timestamp": "string", "duration": { "pause": "boolean", "value": "string" } }
}
```

> `workbench.required_parts` is **not authored** — it is derived at load from every item whose
> `is_assembly_part` is `true`. The full room graph, item matrix and the server's initial
> filesystem live in `../data/default.json`; the schema above mirrors it rather than replacing it.
