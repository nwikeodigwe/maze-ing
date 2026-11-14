"""Tests for apt, adduser, usermod and rsync."""
from tests.support import _connected_shell

def test_apt_update_and_upgrade(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    assert server_shell.state.system["pkg_index_updated"] is True
    server_shell.execute("apt upgrade -y")
    assert server_shell.state.system["pkg_upgraded"] is True


def test_apt_upgrade_before_update_does_not_satisfy_the_step(server_shell):
    _connected_shell(server_shell)
    result = server_shell.execute("apt upgrade")
    assert result.output == "0 upgraded, 0 newly installed, 0 to remove"
    assert server_shell.state.system["pkg_upgraded"] is False


def test_apt_upgrade_without_yes_prompts_for_confirmation(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    result = server_shell.execute("apt upgrade")
    assert result.prompt is not None
    assert "Do you want to continue?" in result.prompt
    server_shell.answer("y")
    assert server_shell.state.system["pkg_upgraded"] is True


def test_adduser_and_usermod_and_key_copy(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("adduser maze-admin")
    server_shell.answer("secret")
    server_shell.answer("secret")
    server_shell.answer("")
    assert server_shell.state.system["users"]["maze-admin"]["sudo"] is False

    server_shell.execute("usermod -aG sudo maze-admin")
    assert server_shell.state.system["users"]["maze-admin"]["sudo"] is True

    server_shell.execute("rsync --archive --chown=maze-admin:maze-admin ~/.ssh /home/maze-admin")
    assert server_shell.state.system["users"]["maze-admin"]["has_ssh_key"] is True
    assert server_shell.state.system["admin_user"] == "maze-admin"


def test_usermod_without_a_flag_warns(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("adduser maze-admin")
    server_shell.answer("secret")
    server_shell.answer("secret")
    server_shell.answer("")
    result = server_shell.execute("usermod -G sudo maze-admin")
    assert "usermod" in result.output
    assert server_shell.state.system["users"]["maze-admin"]["sudo"] is False


def test_answering_a_sub_prompt_asks_the_next_question(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("adduser maze-admin")

    result = server_shell.answer("secret")

    assert result.prompt == "Retype new password: "
    assert server_shell.state.session["pending_prompt"] is not None

    result = server_shell.answer("secret")
    assert result.prompt == "Is the information correct? [Y/n] "

    result = server_shell.answer("")
    assert result.prompt is None
    assert server_shell.state.session["pending_prompt"] is None


def test_apt_without_an_operation(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("apt").output == "apt: no operation specified"


def test_apt_install_of_an_unknown_package(server_shell):
    _connected_shell(server_shell)
    assert "Unable to locate package" in server_shell.execute("apt install bogus").output


def test_apt_invalid_operation(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("apt frobnicate").output == "apt: invalid operation 'frobnicate'"


def test_adduser_password_mismatch_reprompts(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("adduser maze-admin")
    first = server_shell.answer("secret")
    assert first.prompt == "Retype new password: "
    second = server_shell.answer("different")
    assert second.prompt == "New password: "
    assert server_shell.state.system["users"]["maze-admin"] is not None
