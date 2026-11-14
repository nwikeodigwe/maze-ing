"""Tests for the server-provisioning state view."""

from src.server_state import (
    ServerState,
    parse_hosts,
    parse_netplan,
    parse_nginx_site,
    parse_sshd_config,
)


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
        "installed": True,
        "running": True,
        "enabled": True,
        "port": 22,
    }
    assert template["system"]["services"]["nginx"] == {
        "installed": False,
        "running": False,
        "enabled": False,
        "port": 80,
    }
    assert template["system"]["health_verified"] == {
        "service_status_checked": False,
        "ports_checked": False,
        "logs_or_http_checked": False,
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
    assert parse_hosts("127.0.0.1 localhost\n", "maze-server.thuas.nl") == {
        "mapped_fqdn": False
    }
    assert parse_hosts(
        "127.0.0.1 localhost\n127.0.1.1 maze-server.thuas.nl maze-server\n",
        "maze-server.thuas.nl",
    ) == {"mapped_fqdn": True}


def test_parse_netplan_reports_static_ip_and_syntax():
    good = (
        "network:\n  version: 2\n  ethernets:\n    eth0:\n      addresses:\n"
        "        - 10.11.7.42/24\n"
    )
    assert parse_netplan(good, "10.11.7.42") == {"static_ip_set": True, "syntax_valid": True}
    bad = "network:\n  version: 2\n  ethernets:\n   eth0:\n      dhcp4: true\n"
    assert parse_netplan(bad, "10.11.7.42") == {"static_ip_set": False, "syntax_valid": False}


def test_parse_nginx_site_requires_a_server_block():
    assert parse_nginx_site("server {\n  listen 80;\n  root /var/www/maze;\n}\n") == {
        "configured": True,
        "syntax_valid": True,
    }
    assert parse_nginx_site("server {\n  listen 80;\n  root /var/www/maze\n") == {
        "configured": False,
        "syntax_valid": False,
    }


def test_steps_report_all_eleven_progression_steps():
    state = ServerState(ServerState.default())
    steps = state.steps()
    assert len(steps) == 11
    assert [step.id for step in steps] == [
        "ssh",
        "packages",
        "admin_user",
        "ssh_hardening",
        "firewall",
        "host_network",
        "time_sync",
        "nginx",
        "permissions",
        "daemons",
        "verification",
    ]
    assert not any(step.done for step in steps)
    assert state.complete is False


def test_set_file_content_rederives_the_parsed_block():
    state = ServerState(ServerState.default())
    state.set_file_content(
        "/etc/ssh/sshd_config",
        "PermitRootLogin no\nPasswordAuthentication no\nPort 22\n",
    )
    parsed = state.filesystem["/etc/ssh/sshd_config"]["parsed"]
    assert parsed["PermitRootLogin"] == "no"
    assert parsed["syntax_valid"] is True


def test_set_file_content_marks_invalid_syntax():
    state = ServerState(ServerState.default())
    state.set_file_content("/etc/ssh/sshd_config", "PermitRootLogin no\n")
    assert state.filesystem["/etc/ssh/sshd_config"]["parsed"]["syntax_valid"] is False


def test_steps_turn_complete_once_every_requirement_is_met():
    state = ServerState(ServerState.default())
    state.session["connected_via_ssh"] = True
    state.system["known_hosts"].append("10.11.7.42")
    state.system["pkg_index_updated"] = True
    state.system["pkg_upgraded"] = True
    state.system["admin_user"] = "maze-admin"
    state.system["users"]["maze-admin"] = {"sudo": True, "has_ssh_key": True}
    state.set_file_content(
        "/etc/ssh/sshd_config",
        "PermitRootLogin no\nPasswordAuthentication no\nPort 22\n",
    )
    state.system["services"]["sshd"]["port"] = 22
    state.system["firewall"].update(
        {"active": True, "default_incoming": "deny", "default_outgoing": "allow"}
    )
    state.system["firewall"]["allowed_ports"] = [22, 80, 443]
    state.system["hostname"] = "maze-server.thuas.nl"
    state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server.thuas.nl maze-server\n",
    )
    state.set_file_content(
        "/etc/netplan/50-cloud-init.yaml",
        "network:\n  version: 2\n  ethernets:\n    eth0:\n      addresses:\n"
        "        - 10.11.7.42/24\n",
    )
    state.system["ntp_synced"] = True
    state.system["services"]["nginx"]["installed"] = True
    state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    state.filesystem["/etc/nginx/sites-available/app"]["parsed"]["enabled"] = True
    state.filesystem["/etc/nginx/sites-enabled/app"] = {
        "type": "link",
        "target": "/etc/nginx/sites-available/app",
    }
    state.filesystem["/var/www/maze"] = {
        "type": "dir",
        "perms": "755",
        "owner": "maze-admin:www-data",
    }
    state.system["services"]["nginx"].update({"enabled": True, "running": True})
    state.system["health_verified"] = {
        "service_status_checked": True,
        "ports_checked": True,
        "logs_or_http_checked": True,
    }

    assert state.complete is True
    assert all(step.done for step in state.steps())
