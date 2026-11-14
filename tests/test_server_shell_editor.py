"""Tests for nano, vim and sed."""
from tests.support import _connected_shell

def test_nano_saves_the_edited_file(server_shell):
    _connected_shell(server_shell)
    server_shell.state.set_file_content(
        "/etc/ssh/sshd_config",
        "PermitRootLogin yes\nPasswordAuthentication yes\nPort 22\n",
    )
    server_shell._editor = lambda text: (
        True,
        "PermitRootLogin no\nPasswordAuthentication no\nPort 22\n",
    )

    result = server_shell.execute("nano /etc/ssh/sshd_config")

    assert "written" in result.output
    parsed = server_shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]
    assert parsed["PermitRootLogin"] == "no"
    assert parsed["syntax_valid"] is True


def test_nano_on_a_missing_file_reports_the_error(server_shell):
    _connected_shell(server_shell)
    result = server_shell.execute("nano /etc/nope/file")
    assert "No such file or directory" in result.output


def test_sed_edits_a_file_in_place(server_shell):
    _connected_shell(server_shell)
    server_shell.state.set_file_content(
        "/etc/ssh/sshd_config",
        "PermitRootLogin yes\nPasswordAuthentication yes\nPort 22\n",
    )

    server_shell.execute("sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config")

    parsed = server_shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]
    assert parsed["PermitRootLogin"] == "no"


def test_nano_without_a_file(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("nano").output == "usage: nano <file>"


def test_vim_is_an_alias_for_nano(server_shell):
    _connected_shell(server_shell)
    server_shell._editor = lambda text: (True, "PermitRootLogin no")
    server_shell.execute("vim /etc/ssh/sshd_config")
    assert "PermitRootLogin no" in server_shell.state.filesystem["/etc/ssh/sshd_config"]["content"]


def test_apt_get_is_an_alias_for_apt(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt-get update")
    assert server_shell.state.system["pkg_index_updated"] is True


def test_netstat_is_an_alias_for_ss(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("netstat -tulpn")
    assert server_shell.state.system["health_verified"]["ports_checked"] is True


def test_sed_reports_a_missing_file(server_shell):
    _connected_shell(server_shell)
    assert "can't read" in server_shell.execute("sed -i 's/a/b/' /etc/nope").output
