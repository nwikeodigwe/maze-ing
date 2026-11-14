"""Typed view over the game state's ``server`` section.

The section holds the Lab D 2001 provisioning challenge: the machine the
player is on, the server's filesystem, and the system state the eleven steps
are evaluated against. Everything here is plain JSON so it can live inside
``state`` and be persisted with the rest of the game.

Config files are stored as text and their structured fields are *derived* from
that text by a narrow per-file parser. The parsers deliberately check only the
structure the game cares about rather than validating real sshd/nginx/YAML.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

SERVER_IP = "10.11.7.42"
SERVER_HOSTNAME = "maze-server"
SERVER_FQDN = "maze-server.thuas.nl"
NGINX_ROOT = "/var/www/maze"
LOCAL_MACHINE = "thuas-workstation"
LOCAL_USER = "player"

_SSHD_KEYS = ("PermitRootLogin", "PasswordAuthentication", "Port")


@dataclass(frozen=True)
class ServerStep:
    """One provisioning step and whether the player has finished it.

    Attributes:
        id: Stable snake_case identifier for the step.
        title: Short human-readable title.
        hint: One-line coaching shown while the step is incomplete.
        done: True when the step's requirements are met.
    """

    id: str
    title: str
    hint: str
    done: bool


def parse_sshd_config(content: str) -> dict[str, Any]:
    """Parse an sshd config into the fields the challenge tracks.

    Args:
        content: The file's text.

    Returns:
        ``PermitRootLogin``, ``PasswordAuthentication``, ``Port`` and
        ``syntax_valid``. A file missing a required directive is invalid.
    """
    values: dict[str, Any] = {
        "PermitRootLogin": "",
        "PasswordAuthentication": "",
        "Port": 22,
        "syntax_valid": True,
    }
    seen: set[str] = set()
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or parts[0] not in _SSHD_KEYS:
            values["syntax_valid"] = False
            continue
        key, value = parts[0], parts[1].strip()
        if key in seen:
            values["syntax_valid"] = False
            continue
        seen.add(key)
        if key == "Port":
            if not value.isdigit() or int(value) <= 0:
                values["syntax_valid"] = False
                continue
            values["Port"] = int(value)
        else:
            values[key] = value
    for key in _SSHD_KEYS:
        if key not in seen:
            values["syntax_valid"] = False
    return values


def parse_hosts(content: str, hostname: str) -> dict[str, Any]:
    """Report whether a hostname is mapped in an hosts file.

    Args:
        content: The file's text.
        hostname: The fully qualified name that should be mapped.

    Returns:
        ``mapped_fqdn``.
    """
    mapped = False
    for raw in content.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) >= 2 and hostname in fields[1:]:
            mapped = True
    return {"mapped_fqdn": mapped}


def parse_netplan(content: str, ip: str) -> dict[str, Any]:
    """Report whether a netplan file is well formed and sets a static address.

    Args:
        content: The file's text.
        ip: The address the server is expected to keep.

    Returns:
        ``static_ip_set`` and ``syntax_valid``.
    """
    syntax_valid = True
    has_network = False
    addresses_indent: int | None = None
    static = False
    for raw in content.splitlines():
        if "\t" in raw:
            syntax_valid = False
            continue
        stripped = raw.strip()
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            syntax_valid = False
        if stripped == "network:" and indent == 0:
            has_network = True
        if stripped == "addresses:":
            addresses_indent = indent
            continue
        if addresses_indent is not None:
            if indent <= addresses_indent:
                addresses_indent = None
            elif ip in raw:
                static = True
    if not has_network:
        syntax_valid = False
    return {"static_ip_set": static and syntax_valid, "syntax_valid": syntax_valid}


def parse_nginx_site(content: str) -> dict[str, Any]:
    """Report whether an nginx site block is well formed and points at the app.

    Args:
        content: The file's text.

    Returns:
        ``configured`` and ``syntax_valid``.
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    syntax_valid = bool(lines) and lines[0] == "server {" and lines[-1] == "}"
    if syntax_valid:
        for line in lines[1:-1]:
            if not line.endswith(";"):
                syntax_valid = False
                break
    configured = (
        syntax_valid
        and "listen 80;" in content
        and f"root {NGINX_ROOT};" in content
    )
    return {"configured": configured, "syntax_valid": syntax_valid}


def _file(content: str, perms: str, owner: str, parsed: dict[str, Any]) -> dict[str, Any]:
    """Build a file node."""
    return {
        "type": "file",
        "content": content,
        "perms": perms,
        "owner": owner,
        "parsed": parsed,
    }


def _dir(perms: str, owner: str) -> dict[str, Any]:
    """Build a directory node."""
    return {"type": "dir", "perms": perms, "owner": owner}


_DEFAULT_TEMPLATE: dict[str, Any] = {
    "session": {
        "machine": LOCAL_MACHINE,
        "user": LOCAL_USER,
        "cwd": "/home/player",
        "prompt_symbol": "$",
        "connected_via_ssh": False,
        "pending_prompt": None,
    },
    "filesystem": {
        "/": _dir("755", "root:root"),
        "/etc": _dir("755", "root:root"),
        "/etc/ssh": _dir("755", "root:root"),
        "/etc/ssh/sshd_config": _file(
            "PermitRootLogin yes\nPasswordAuthentication yes\nPort 22\n",
            "600",
            "root:root",
            parse_sshd_config(
                "PermitRootLogin yes\nPasswordAuthentication yes\nPort 22\n"
            ),
        ),
        "/etc/hosts": _file(
            "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server\n",
            "644",
            "root:root",
            parse_hosts("127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server\n", SERVER_FQDN),
        ),
        "/etc/netplan": _dir("755", "root:root"),
        "/etc/netplan/50-cloud-init.yaml": _file(
            "network:\n  version: 2\n  ethernets:\n    eth0:\n      dhcp4: true\n",
            "644",
            "root:root",
            parse_netplan(
                "network:\n  version: 2\n  ethernets:\n    eth0:\n      dhcp4: true\n",
                SERVER_IP,
            ),
        ),
        "/etc/nginx": _dir("755", "root:root"),
        "/etc/nginx/sites-available": _dir("755", "root:root"),
        "/etc/nginx/sites-enabled": _dir("755", "root:root"),
        "/home": _dir("755", "root:root"),
        "/home/player": _dir("755", "player:player"),
        "/home/player/.ssh": _dir("700", "player:player"),
        "/home/player/.ssh/id_ed25519": _file(
            "-----BEGIN OPENSSH PRIVATE KEY-----\nplayer-lab-key\n-----END OPENSSH PRIVATE KEY-----\n",
            "600",
            "player:player",
            {},
        ),
        "/root": _dir("700", "root:root"),
        "/root/.ssh": _dir("700", "root:root"),
        "/root/.ssh/authorized_keys": _file("", "600", "root:root", {}),
        "/var": _dir("755", "root:root"),
        "/var/log": _dir("755", "root:root"),
        "/var/log/nginx": _dir("755", "root:root"),
        "/var/log/nginx/access.log": _file("", "644", "root:root", {}),
        "/var/www": _dir("755", "root:root"),
    },
    "system": {
        "ip_address": SERVER_IP,
        "known_hosts": [],
        "pkg_index_updated": False,
        "pkg_upgraded": False,
        "admin_user": None,
        "users": {"root": {"sudo": True, "has_ssh_key": True}},
        "hostname": SERVER_HOSTNAME,
        "timezone": "Etc/UTC",
        "ntp_synced": False,
        "firewall": {
            "active": False,
            "default_incoming": "allow",
            "default_outgoing": "allow",
            "allowed_ports": [],
        },
        "services": {
            "sshd": {"installed": True, "running": True, "enabled": True, "port": 22},
            "nginx": {"installed": False, "running": False, "enabled": False, "port": 80},
        },
        "health_verified": {
            "service_status_checked": False,
            "ports_checked": False,
            "logs_or_http_checked": False,
        },
    },
}

_PARSERS = {
    "/etc/ssh/sshd_config": lambda content: parse_sshd_config(content),
    "/etc/nginx/sites-available/app": lambda content: parse_nginx_site(content),
}


class ServerState:
    """Typed view over the ``server`` section of the game state.

    The view mutates the dict it was given in place, so changes made through
    it are visible to whoever owns the game state and get persisted with it.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """Wrap the live section.

        Args:
            data: The ``server`` dict from the game state.
        """
        self.data = data

    @staticmethod
    def default() -> dict[str, Any]:
        """Return a fresh copy of the default server template."""
        return copy.deepcopy(_DEFAULT_TEMPLATE)

    @property
    def session(self) -> dict[str, Any]:
        """The active machine and session."""
        return self.data["session"]

    @property
    def filesystem(self) -> dict[str, Any]:
        """The virtual filesystem, keyed by absolute path."""
        return self.data["filesystem"]

    @property
    def system(self) -> dict[str, Any]:
        """The server's system state."""
        return self.data["system"]

    def set_file_content(self, path: str, content: str) -> None:
        """Write a file's text and re-derive its parsed fields.

        A file that does not exist yet is created, as long as its parent
        directory does — that is how the player writes the nginx site block.

        Args:
            path: Absolute path of the file.
            content: The new file text.

        Raises:
            KeyError: When the parent directory does not exist.
        """
        node = self.filesystem.get(path)
        if node is None:
            parent = path.rsplit("/", 1)[0] or "/"
            if parent not in self.filesystem:
                raise KeyError(path)
            node = _file(content, "644", "root:root", {})
            self.filesystem[path] = node
        node["content"] = content
        node["parsed"] = self._parse(path, content)

    def _parse(self, path: str, content: str) -> dict[str, Any]:
        """Derive the structured fields for one file's text."""
        if path == "/etc/hosts":
            return parse_hosts(content, SERVER_FQDN)
        if path == "/etc/netplan/50-cloud-init.yaml":
            return parse_netplan(content, self.system.get("ip_address", SERVER_IP))
        if path == "/etc/nginx/sites-available/app":
            return parse_nginx_site(content)
        parser = _PARSERS.get(path)
        return parser(content) if parser else {}

    def steps(self) -> list[ServerStep]:
        """Return the eleven provisioning steps and their completion state."""
        system = self.system
        filesystem = self.filesystem
        sshd = filesystem.get("/etc/ssh/sshd_config", {}).get("parsed", {})
        hosts = filesystem.get("/etc/hosts", {}).get("parsed", {})
        netplan = filesystem.get("/etc/netplan/50-cloud-init.yaml", {}).get("parsed", {})
        site = filesystem.get("/etc/nginx/sites-available/app", {}).get("parsed", {})
        webroot = filesystem.get("/var/www/maze", {})
        firewall = system.get("firewall", {})
        services = system.get("services", {})
        health = system.get("health_verified", {})
        sshd_service = services.get("sshd", {})
        nginx_service = services.get("nginx", {})
        admin = system.get("admin_user")
        admin_entry = system.get("users", {}).get(admin, {}) if admin else {}
        ssh_port = sshd_service.get("port", 22)
        allowed = firewall.get("allowed_ports", [])

        return [
            ServerStep(
                "ssh",
                "Connect to the server",
                f"ssh -i ~/.ssh/id_ed25519 root@{SERVER_IP}",
                SERVER_IP in system.get("known_hosts", []),
            ),
            ServerStep(
                "packages",
                "Update system packages",
                "apt update && apt upgrade",
                bool(system.get("pkg_index_updated")) and bool(system.get("pkg_upgraded")),
            ),
            ServerStep(
                "admin_user",
                "Create a sudo user with an SSH key",
                "adduser <user>, usermod -aG sudo <user>, then copy ~/.ssh to the new home",
                bool(admin)
                and bool(admin_entry.get("sudo"))
                and bool(admin_entry.get("has_ssh_key")),
            ),
            ServerStep(
                "ssh_hardening",
                "Harden SSH",
                "set PermitRootLogin no and PasswordAuthentication no "
                "in /etc/ssh/sshd_config, then systemctl reload sshd",
                sshd.get("PermitRootLogin") == "no"
                and sshd.get("PasswordAuthentication") == "no"
                and bool(sshd.get("syntax_valid"))
                and sshd.get("Port", 22) == ssh_port,
            ),
            ServerStep(
                "firewall",
                "Configure the firewall",
                f"ufw default deny incoming, ufw allow {ssh_port}/tcp, then ufw enable",
                bool(firewall.get("active"))
                and firewall.get("default_incoming") == "deny"
                and firewall.get("default_outgoing") == "allow"
                and ssh_port in allowed
                and 80 in allowed
                and 443 in allowed,
            ),
            ServerStep(
                "host_network",
                "Set the hostname and static IP",
                f"hostnamectl set-hostname {SERVER_FQDN}, map it in /etc/hosts, then netplan apply",
                system.get("hostname") == SERVER_FQDN
                and bool(hosts.get("mapped_fqdn"))
                and bool(netplan.get("static_ip_set")),
            ),
            ServerStep(
                "time_sync",
                "Synchronise the clock",
                "timedatectl set-timezone UTC && timedatectl set-ntp true",
                bool(system.get("ntp_synced")),
            ),
            ServerStep(
                "nginx",
                "Install and configure nginx",
                "apt install nginx, write a server block for /var/www/maze, enable the site, then nginx -t",
                bool(nginx_service.get("installed"))
                and bool(site.get("configured"))
                and bool(site.get("syntax_valid"))
                and "/etc/nginx/sites-enabled/app" in filesystem
                and filesystem.get("/etc/nginx/sites-enabled/app", {}).get(
                    "type"
                )
                == "link",
            ),
            ServerStep(
                "permissions",
                "Set web root permissions",
                "mkdir -p /var/www/maze, chown -R <admin>:www-data, chmod -R 755",
                webroot.get("type") == "dir"
                and str(webroot.get("owner", "")).endswith(":www-data")
                and str(webroot.get("perms", "")) in ("755", "750"),
            ),
            ServerStep(
                "daemons",
                "Start the daemon",
                "systemctl enable --now nginx",
                bool(nginx_service.get("enabled")) and bool(nginx_service.get("running")),
            ),
            ServerStep(
                "verification",
                "Verify the service",
                "systemctl status nginx, ss -tulpn, then curl -I http://localhost",
                bool(health.get("service_status_checked"))
                and bool(health.get("ports_checked"))
                and bool(health.get("logs_or_http_checked")),
            ),
        ]

    @property
    def complete(self) -> bool:
        """True when every provisioning step is finished."""
        return all(step.done for step in self.steps())
