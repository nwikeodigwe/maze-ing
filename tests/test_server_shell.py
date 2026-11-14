"""Tests for the server-provisioning shell."""

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
    assert shell.execute("groups").output == "player"


def test_sudo_is_required_for_privileged_commands(shell):
    result = shell.execute("apt update")
    assert result.output == "Permission denied (are you root?)"
    assert shell.state.system["pkg_index_updated"] is False


def test_unknown_flags_do_not_change_state(shell):
    result = shell.execute("ls --bogus")
    assert "unrecognized option" in result.output


def test_trailing_whitespace_is_tolerated(shell):
    assert shell.execute("pwd   ").output == "/home/player"


def test_answering_the_host_key_prompt_connects_to_the_server(shell):
    shell.state.session["pending_prompt"] = {
        "kind": "ssh_host_key",
        "host": "10.11.7.42",
        "user": "root",
    }

    shell.answer("yes")

    assert shell.state.session["connected_via_ssh"] is True
    assert shell.state.session["machine"] == "maze-server"
    assert shell.state.session["user"] == "root"
    assert shell.state.session["cwd"] == "/root"
    assert shell.state.session["prompt_symbol"] == "#"
    assert "10.11.7.42" in shell.state.system["known_hosts"]


def test_answering_y_to_the_host_key_prompt_asks_again(shell):
    shell.state.session["pending_prompt"] = {
        "kind": "ssh_host_key",
        "host": "10.11.7.42",
        "user": "root",
    }

    result = shell.answer("y")

    assert result.prompt == "Please type 'yes', 'no' or the fingerprint: "
    assert shell.state.session["connected_via_ssh"] is False


def test_a_command_answers_the_pending_prompt(shell):
    shell.state.session["pending_prompt"] = {
        "kind": "ssh_host_key",
        "host": "10.11.7.42",
        "user": "root",
    }

    shell.execute("yes")

    assert shell.state.session["connected_via_ssh"] is True


def _connected_shell(shell):
    """Connect the shell to the server, accepting the host key."""
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    shell.answer("yes")
    return shell

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
    _connected_shell(shell)
    shell.execute("apt update")
    assert shell.state.system["pkg_index_updated"] is True
    shell.execute("apt upgrade -y")
    assert shell.state.system["pkg_upgraded"] is True


def test_apt_upgrade_before_update_does_not_satisfy_the_step(shell):
    _connected_shell(shell)
    result = shell.execute("apt upgrade")
    assert result.output == "0 upgraded, 0 newly installed, 0 to remove"
    assert shell.state.system["pkg_upgraded"] is False


def test_apt_upgrade_without_yes_prompts_for_confirmation(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    result = shell.execute("apt upgrade")
    assert result.prompt is not None
    assert "Do you want to continue?" in result.prompt
    shell.answer("y")
    assert shell.state.system["pkg_upgraded"] is True


def test_adduser_and_usermod_and_key_copy(shell):
    _connected_shell(shell)
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
    _connected_shell(shell)
    shell.execute("adduser maze-admin")
    shell.answer("secret")
    shell.answer("secret")
    shell.answer("")
    result = shell.execute("usermod -G sudo maze-admin")
    assert "usermod" in result.output
    assert shell.state.system["users"]["maze-admin"]["sudo"] is False


def test_systemctl_reload_sshd_requires_valid_syntax(shell):
    _connected_shell(shell)
    shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]["syntax_valid"] = False
    result = shell.execute("systemctl reload sshd")
    assert result.output == (
        "Job for ssh.service failed because the control process exited with error code."
    )


def test_ssh_lockout_blocks_a_later_connection(shell):
    _connected_shell(shell)
    shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )
    shell.execute("systemctl reload sshd")
    shell.execute("exit")
    result = shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    assert "Permission denied" in result.output

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
    shell.execute("mkdir -p /var/www/maze")
    shell.execute("chmod -R 755 /var/www/maze")

    shell.execute("systemctl status nginx")
    assert shell.state.system["health_verified"]["service_status_checked"] is True

    shell.execute("ss -tulpn")
    assert shell.state.system["health_verified"]["ports_checked"] is True

    shell.execute("curl -I http://localhost")
    assert shell.state.system["health_verified"]["logs_or_http_checked"] is True

def test_checklist_lists_all_eleven_steps_with_progress(shell):
    output = shell.execute("checklist").output
    assert len(output.splitlines()) == 22
    assert "[x]" not in output
    assert "[ ]" in output
    assert "Step 1" in output
    assert "ssh -i ~/.ssh/id_ed25519 root@10.11.7.42" in output

    _connected_shell(shell)
    output = shell.execute("checklist").output
    assert "[x] Step 1" in output


def test_checklist_marks_completed_steps(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt upgrade -y")
    output = shell.execute("checklist").output
    assert "[x]" in output


def test_checklist_hints_the_next_incomplete_step(shell):
    _connected_shell(shell)
    output = shell.execute("checklist").output
    assert "Step 5" in output
    assert "ufw" in output
