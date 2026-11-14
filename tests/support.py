"""Shared helpers for the server-shell tests.

Helpers are plain functions/constants rather than fixtures, so test modules
import them directly; fixtures live in ``conftest.py``.
"""

#: The exact list of commands that provisions the server end-to-end.
FULL_PROVISIONING_SCRIPT = [
    "ssh -i ~/.ssh/id_ed25519 root@10.11.7.42",
    "yes",
    "apt update",
    "apt upgrade -y",
    "adduser maze-admin",
    "secret",
    "secret",
    "",
    "usermod -aG sudo maze-admin",
    "rsync --archive --chown=maze-admin:maze-admin ~/.ssh /home/maze-admin",
    "nano /etc/ssh/sshd_config",
    "sshd -t",
    "systemctl reload sshd",
    "ufw default deny incoming",
    "ufw default allow outgoing",
    "ufw allow 22/tcp",
    "ufw allow 80/tcp",
    "ufw allow 443/tcp",
    "ufw enable",
    "y",
    "hostnamectl set-hostname maze-server.thuas.nl",
    "nano /etc/hosts",
    "nano /etc/netplan/50-cloud-init.yaml",
    "netplan apply",
    "timedatectl set-timezone UTC",
    "timedatectl set-ntp true",
    "apt install nginx",
    "nano /etc/nginx/sites-available/app",
    "ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app",
    "nginx -t",
    "mkdir -p /var/www/maze",
    "chown -R maze-admin:www-data /var/www/maze",
    "chmod -R 755 /var/www/maze",
    "systemctl enable --now nginx",
    "systemctl status nginx",
    "ss -tulpn",
    "curl -I http://localhost",
]


def _connected_shell(shell):
    """Connect the shell to the server, accepting the host key."""
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    return shell


def _scripted_editor(shell):
    """An editor that writes the correct content into each config file."""
    edits = {
        "/etc/ssh/sshd_config": (
            "PermitRootLogin no\nPasswordAuthentication no\nPort 22\n"
        ),
        "/etc/hosts": (
            "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server.thuas.nl maze-server\n"
        ),
        "/etc/netplan/50-cloud-init.yaml": (
            "network:\n  version: 2\n  ethernets:\n    eth0:\n      addresses:\n"
            "        - 10.11.7.42/24\n      gateway4: 10.11.7.1\n"
            "      nameservers:\n        addresses: [1.1.1.1, 8.8.8.8]\n"
        ),
        "/etc/nginx/sites-available/app": (
            "server {\n  listen 80;\n  root /var/www/maze;\n}\n"
        ),
    }

    def editor(text):
        for path, content in edits.items():
            if text == shell.state.filesystem.get(path, {}).get("content", text):
                return True, content
        return True, text

    return editor