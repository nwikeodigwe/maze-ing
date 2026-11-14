"""Tests for ufw, hostnamectl, netplan and timedatectl."""
from tests.support import _connected_shell

def test_ufw_default_policies_and_allow_rules(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("ufw default deny incoming")
    assert server_shell.state.system["firewall"]["default_incoming"] == "deny"
    server_shell.execute("ufw default allow outgoing")
    assert server_shell.state.system["firewall"]["default_outgoing"] == "allow"
    server_shell.execute("ufw allow 22/tcp")
    server_shell.execute("ufw allow 80/tcp")
    server_shell.execute("ufw allow 443/tcp")
    assert set(server_shell.state.system["firewall"]["allowed_ports"]) == {22, 80, 443}


def test_ufw_enable_prompts_for_confirmation(server_shell):
    _connected_shell(server_shell)
    result = server_shell.execute("ufw enable")
    assert result.prompt is not None
    assert "Command may disrupt existing ssh connections" in result.prompt
    assert server_shell.state.system["firewall"]["active"] is False


def test_ufw_enable_without_the_ssh_port_severs_the_session(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("ufw default deny incoming")
    server_shell.execute("ufw enable")
    result = server_shell.answer("y")
    assert "Broken pipe" in result.output
    assert server_shell.state.session["machine"] == "thuas-workstation"
    assert server_shell.state.system["firewall"]["active"] is False
    assert server_shell.state.system["firewall"]["default_incoming"] == "allow"


def test_ufw_enable_with_the_ssh_port_succeeds(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("ufw default deny incoming")
    server_shell.execute("ufw allow 22/tcp")
    server_shell.execute("ufw enable")
    server_shell.answer("y")
    assert server_shell.state.system["firewall"]["active"] is True
    assert server_shell.state.session["machine"] == "maze-server"


def test_hostnamectl_and_hosts_mapping(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("hostnamectl set-hostname maze-server.thuas.nl")
    assert server_shell.state.system["hostname"] == "maze-server.thuas.nl"
    server_shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server.thuas.nl maze-server\n",
    )
    assert server_shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is True


def test_netplan_apply_requires_valid_yaml(server_shell):
    _connected_shell(server_shell)
    server_shell.state.set_file_content(
        "/etc/netplan/50-cloud-init.yaml",
        "network:\n  version: 2\n  ethernets:\n   eth0:\n      dhcp4: true\n",
    )
    result = server_shell.execute("netplan apply")
    assert result.output == (
        "/etc/netplan/50-cloud-init.yaml:5:7: Error in network definition: invalid YAML"
    )


def test_timedatectl_sets_ntp(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("timedatectl set-timezone UTC")
    assert server_shell.state.system["timezone"] == "Etc/UTC"
    server_shell.execute("timedatectl set-ntp true")
    assert server_shell.state.system["ntp_synced"] is True


def test_timedatectl_status_shows_the_clock(server_shell):
    _connected_shell(server_shell)
    output = server_shell.execute("timedatectl status").output
    assert "System clock synchronized: no" in output


def test_hosts_mapping_accepts_the_static_address(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("hostnamectl set-hostname maze-server.thuas.nl")
    server_shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n10.11.7.42\tmaze-server.thuas.nl maze-server\n",
    )

    assert server_shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is True


def test_hosts_mapping_requires_the_fqdn(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("hostnamectl set-hostname maze-server.thuas.nl")
    server_shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server\n",
    )

    assert server_shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is False


def test_hosts_mapping_is_rederived_when_the_hostname_changes(server_shell):
    _connected_shell(server_shell)
    server_shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server.thuas.nl maze-server\n",
    )
    server_shell.execute("hostnamectl set-hostname maze-server.thuas.nl")

    assert server_shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is True


def test_ufw_status_before_enabling(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("ufw status").output == "Status: inactive"


def test_ufw_without_arguments(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("ufw").output == "ufw: missing command"


def test_ufw_allow_named_rules(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("ufw allow OpenSSH")
    server_shell.execute("ufw allow 'Nginx Full'")
    allowed = server_shell.state.system["firewall"]["allowed_ports"]
    assert 22 in allowed and 80 in allowed and 443 in allowed


def test_ufw_invalid_default_policy(server_shell):
    _connected_shell(server_shell)
    assert "invalid direction" in server_shell.execute("ufw default deny sideways").output


def test_hostnamectl_requires_a_name(server_shell):
    _connected_shell(server_shell)
    assert "usage" in server_shell.execute("hostnamectl").output.lower()


def test_timedatectl_unknown_operation(server_shell):
    _connected_shell(server_shell)
    assert "Unknown operation" in server_shell.execute("timedatectl frobnicate").output
