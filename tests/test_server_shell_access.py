"""Tests for ssh, su, sudo and the host-key sub-prompt."""
from tests.support import _connected_shell

def test_answering_the_host_key_prompt_connects_to_the_server(server_shell):
    server_shell.state.session["pending_prompt"] = {
        "kind": "ssh_host_key",
        "host": "10.11.7.42",
        "user": "root",
    }

    server_shell.answer("yes")

    assert server_shell.state.session["connected_via_ssh"] is True
    assert server_shell.state.session["machine"] == "maze-server"
    assert server_shell.state.session["user"] == "root"
    assert server_shell.state.session["cwd"] == "/root"
    assert server_shell.state.session["prompt_symbol"] == "#"
    assert "10.11.7.42" in server_shell.state.system["known_hosts"]


def test_answering_y_to_the_host_key_prompt_asks_again(server_shell):
    server_shell.state.session["pending_prompt"] = {
        "kind": "ssh_host_key",
        "host": "10.11.7.42",
        "user": "root",
    }

    result = server_shell.answer("y")

    assert result.prompt == "Please type 'yes', 'no' or the fingerprint: "
    assert server_shell.state.session["connected_via_ssh"] is False


def test_a_command_answers_the_pending_prompt(server_shell):
    server_shell.state.session["pending_prompt"] = {
        "kind": "ssh_host_key",
        "host": "10.11.7.42",
        "user": "root",
    }

    server_shell.execute("yes")

    assert server_shell.state.session["connected_via_ssh"] is True


def test_ssh_to_the_server_prompts_for_the_host_key(server_shell):
    result = server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    assert result.prompt is not None
    assert "Are you sure you want to continue connecting" in result.prompt
    assert server_shell.state.session["connected_via_ssh"] is False


def test_answering_yes_accepts_the_host_key(server_shell):
    server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    server_shell.answer("yes")
    assert server_shell.state.session["connected_via_ssh"] is True
    assert server_shell.state.session["machine"] == "maze-server"
    assert server_shell.state.session["user"] == "root"
    assert server_shell.state.session["cwd"] == "/root"
    assert server_shell.state.session["prompt_symbol"] == "#"
    assert "10.11.7.42" in server_shell.state.system["known_hosts"]


def test_typing_y_reprompts_for_the_full_word(server_shell):
    server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    result = server_shell.answer("y")
    assert result.prompt is not None
    assert "Please type 'yes', 'no' or the fingerprint" in result.prompt


def test_ssh_without_a_key_is_denied(server_shell):
    result = server_shell.execute("ssh root@10.11.7.42")
    assert result.output == "root@10.11.7.42: Permission denied (publickey)."


def test_ssh_to_the_wrong_address_times_out(server_shell):
    result = server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.99")
    assert result.output == "ssh: connect to host 10.11.7.99 port 22: Connection timed out"


def test_ssh_lockout_only_arms_once_an_admin_key_exists(server_shell):
    # Hardening SSH before any admin account exists must not strand the
    # player: root can still reconnect to create one.
    _connected_shell(server_shell)
    server_shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )
    server_shell.execute("systemctl reload sshd")
    server_shell.execute("exit")
    server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")
    assert server_shell.state.session["connected_via_ssh"] is True


def test_answering_the_host_key_wrongly_asks_again(server_shell):
    server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")

    result = server_shell.answer("y")

    assert result.prompt == "Please type 'yes', 'no' or the fingerprint: "
    assert server_shell.state.session["pending_prompt"] is not None


def test_ssh_still_works_before_an_admin_user_exists(server_shell):
    _connected_shell(server_shell)
    server_shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )

    server_shell.execute("exit")
    result = server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")

    assert "Permission denied" not in result.output
    assert server_shell.state.session["connected_via_ssh"] is True


def test_ssh_denies_root_once_an_admin_user_has_a_key(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("adduser maze-admin")
    server_shell.answer("secret")
    server_shell.answer("secret")
    server_shell.answer("")
    server_shell.execute("usermod -aG sudo maze-admin")
    server_shell.execute(
        "rsync --archive --chown=maze-admin:maze-admin ~/.ssh /home/maze-admin"
    )
    server_shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"].update(
        {"PermitRootLogin": "no", "PasswordAuthentication": "no"}
    )

    server_shell.execute("exit")
    result = server_shell.execute("ssh -i ~/.ssh/id_ed25519 root@10.11.7.42")

    assert "Permission denied" in result.output


def test_su_needs_sudo_rights(server_shell):
    result = server_shell.execute("su - maze-admin")
    assert result.output == "su: Authentication failure"
    assert server_shell.state.session["user"] == "player"


def test_su_without_a_user_is_refused(server_shell):
    _connected_shell(server_shell)
    result = server_shell.execute("su")
    assert result.output == "su: no user specified"
    assert server_shell.state.session["user"] == "root"


def test_ssh_on_the_wrong_port_is_refused(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("exit")

    result = server_shell.execute("ssh -p 9999 -i ~/.ssh/id_ed25519 root@10.11.7.42")

    assert "Connection refused" in result.output
    assert server_shell.state.session["connected_via_ssh"] is False


def test_sudo_with_no_command_is_rejected(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("sudo").output == "sudo: no command given"


def test_sudo_is_denied_for_a_non_sudo_user(server_shell):
    result = server_shell.execute("sudo apt update")
    assert "not in the sudoers file" in result.output


def test_sudo_runs_as_root_when_connected(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("sudo apt update")
    assert server_shell.state.system["pkg_index_updated"] is True


def test_sudo_unknown_command(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("sudo frobnicate").output == (
        "bash: frobnicate: command not found"
    )


def test_su_to_an_unknown_user(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("su - ghoster").output == "su: user 'ghoster' does not exist"


def test_groups_reports_root_and_sudo(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("groups").output == "root sudo"
