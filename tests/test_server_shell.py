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
