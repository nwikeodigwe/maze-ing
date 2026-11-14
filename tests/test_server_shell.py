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


def test_ssh_lockout_only_arms_once_an_admin_key_exists(shell):
    # Hardening SSH before any admin account exists must not strand the
    # player: root can still reconnect to create one.
    _connected_shell(shell)
    shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )
    shell.execute("systemctl reload sshd")
    shell.execute("exit")
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    assert shell.state.session["connected_via_ssh"] is True

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
    # Eleven steps plus a hint on exactly the first incomplete one.
    assert len(output.splitlines()) == 12
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


def test_checklist_hints_only_the_next_incomplete_step(shell):
    _connected_shell(shell)
    output = shell.execute("checklist").output
    assert "Step 2" in output
    assert "apt update && apt upgrade" in output
    # A later step must not be hinted, so the player is not handed a walkthrough.
    assert "ufw default deny incoming" not in output

def test_nano_saves_the_edited_file(shell):
    _connected_shell(shell)
    shell.state.set_file_content(
        "/etc/ssh/sshd_config",
        "PermitRootLogin yes\nPasswordAuthentication yes\nPort 22\n",
    )
    shell._editor = lambda text: (
        True,
        "PermitRootLogin no\nPasswordAuthentication no\nPort 22\n",
    )

    result = shell.execute("nano /etc/ssh/sshd_config")

    assert "written" in result.output
    parsed = shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]
    assert parsed["PermitRootLogin"] == "no"
    assert parsed["syntax_valid"] is True


def test_nano_on_a_missing_file_reports_the_error(shell):
    _connected_shell(shell)
    result = shell.execute("nano /etc/nope/file")
    assert "No such file or directory" in result.output


def test_sed_edits_a_file_in_place(shell):
    _connected_shell(shell)
    shell.state.set_file_content(
        "/etc/ssh/sshd_config",
        "PermitRootLogin yes\nPasswordAuthentication yes\nPort 22\n",
    )

    shell.execute("sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config")

    parsed = shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]
    assert parsed["PermitRootLogin"] == "no"


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


def test_the_challenge_can_be_completed_end_to_end(shell):
    shell._editor = _scripted_editor(shell)

    for command in FULL_PROVISIONING_SCRIPT:
        shell.execute(command)

    assert shell.state.session.get("pending_prompt") is None
    assert shell.state.complete is True
    assert [step.id for step in shell.state.steps() if not step.done] == []
# -- Review fixes ---------------------------------------------------------
# C3: the follow-up prompt must survive the answer, and the room loop must
# keep asking until the shell has no prompt left.
def test_answering_a_sub_prompt_asks_the_next_question(shell):
    _connected_shell(shell)
    shell.execute("adduser maze-admin")

    result = shell.answer("secret")

    assert result.prompt == "Retype new password: "
    assert shell.state.session["pending_prompt"] is not None

    result = shell.answer("secret")
    assert result.prompt == "Is the information correct? [Y/n] "

    result = shell.answer("")
    assert result.prompt is None
    assert shell.state.session["pending_prompt"] is None


def test_answering_the_host_key_wrongly_asks_again(shell):
    shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")

    result = shell.answer("y")

    assert result.prompt == "Please type 'yes', 'no' or the fingerprint: "
    assert shell.state.session["pending_prompt"] is not None


# C1: completing the challenge must survive leaving the server.
def test_completion_survives_leaving_the_server(shell):
    shell._editor = _scripted_editor(shell)
    for command in FULL_PROVISIONING_SCRIPT:
        shell.execute(command)

    assert shell.state.complete is True

    shell.execute("exit")

    assert shell.state.complete is True


# C2: hardening sshd before an admin user exists must not lock the player out.
def test_ssh_still_works_before_an_admin_user_exists(shell):
    _connected_shell(shell)
    shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )

    shell.execute("exit")
    result = shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")

    assert "Permission denied" not in result.output
    assert shell.state.session["connected_via_ssh"] is True


def test_ssh_denies_root_once_an_admin_user_has_a_key(shell):
    _connected_shell(shell)
    shell.execute("adduser maze-admin")
    shell.answer("secret")
    shell.answer("secret")
    shell.answer("")
    shell.execute("usermod -aG sudo maze-admin")
    shell.execute(
        "rsync --archive --chown=maze-admin:maze-admin ~/.ssh /home/maze-admin"
    )
    shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )

    shell.execute("exit")
    result = shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")

    assert "Permission denied" in result.output


# I3: the hosts entry must be matched against the FQDN, whatever address it uses.
def test_hosts_mapping_accepts_the_static_address(shell):
    _connected_shell(shell)
    shell.execute("hostnamectl set-hostname maze-server.thuas.nl")
    shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n10.11.7.42\tmaze-server.thuas.nl maze-server\n",
    )

    assert shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is True


def test_hosts_mapping_requires_the_fqdn(shell):
    _connected_shell(shell)
    shell.execute("hostnamectl set-hostname maze-server.thuas.nl")
    shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server\n",
    )

    assert shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is False


def test_hosts_mapping_is_rederived_when_the_hostname_changes(shell):
    _connected_shell(shell)
    shell.state.set_file_content(
        "/etc/hosts",
        "127.0.0.1\tlocalhost\n127.0.1.1\tmaze-server.thuas.nl maze-server\n",
    )
    shell.execute("hostnamectl set-hostname maze-server.thuas.nl")

    assert shell.state.filesystem["/etc/hosts"]["parsed"]["mapped_fqdn"] is True


# I4: editing the site after linking it must not un-complete the step.
def test_editing_the_site_after_linking_keeps_the_step_done(shell):
    _connected_shell(shell)
    shell.execute("apt update")
    shell.execute("apt install nginx")
    shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    shell.execute(
        "ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app"
    )
    shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n  index index.html;\n}\n",
    )

    steps = {step.id: step for step in shell.state.steps()}
    assert steps["nginx"].done is True


# I5: the documented cp route must work and must not destroy a directory.
def test_cp_into_a_directory_copies_the_file_inside(shell):
    _connected_shell(shell)
    shell.execute("adduser maze-admin")
    shell.answer("secret")
    shell.answer("secret")
    shell.answer("")
    shell.execute("mkdir -p /home/maze-admin/.ssh")
    shell.execute("cp /root/.ssh/authorized_keys /home/maze-admin/.ssh/")
    shell.execute("chown -R maze-admin:maze-admin /home/maze-admin/.ssh")

    assert shell.state.filesystem["/home/maze-admin/.ssh"]["type"] == "dir"
    assert shell.state.system["users"]["maze-admin"]["has_ssh_key"] is True


# I1: su must not be a free root escalation.
def test_su_needs_sudo_rights(shell):
    result = shell.execute("su - maze-admin")
    assert result.output == "su: Authentication failure"
    assert shell.state.session["user"] == "player"


def test_su_without_a_user_is_refused(shell):
    _connected_shell(shell)
    result = shell.execute("su")
    assert result.output == "su: no user specified"
    assert shell.state.session["user"] == "root"


# I2: a wrong port must not connect.
def test_ssh_on_the_wrong_port_is_refused(shell):
    _connected_shell(shell)
    shell.execute("exit")

    result = shell.execute("ssh -p 9999 -i ~/.ssh/id_ed25519 root@10.11.7.42")

    assert "Connection refused" in result.output
    assert shell.state.session["connected_via_ssh"] is False
