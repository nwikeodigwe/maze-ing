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
