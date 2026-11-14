"""Tests for the core command execution, filesystem, help, checklist and end-to-end run."""
from src.utils.shell import ShellResult
from tests.support import FULL_PROVISIONING_SCRIPT, _connected_shell, _scripted_editor

def test_execute_reports_unknown_commands(server_shell):
    assert server_shell.execute("frobnicate").output == "bash: frobnicate: command not found"


def test_execute_reports_unmatched_quotes(server_shell):
    assert server_shell.execute('cat "unterminated').output == "bash: syntax error: unmatched quote"


def test_empty_command_does_nothing(server_shell):
    assert server_shell.execute("") == ShellResult()


def test_prompt_shows_the_local_workstation(server_shell):
    assert server_shell.prompt == "player@thuas-workstation:~$"


def test_pwd_and_cd_navigate_the_tree(server_shell):
    assert server_shell.execute("pwd").output == "/home/player"
    assert server_shell.execute("cd /etc").output == ""
    assert server_shell.execute("pwd").output == "/etc"
    assert server_shell.execute("cd ..").output == ""
    assert server_shell.execute("pwd").output == "/"


def test_ls_lists_a_directory(server_shell):
    output = server_shell.execute("ls /etc/ssh").output
    assert "sshd_config" in output


def test_cat_prints_file_contents(server_shell):
    output = server_shell.execute("cat /etc/ssh/sshd_config").output
    assert "PermitRootLogin yes" in output


def test_cat_reports_a_missing_file(server_shell):
    assert "No such file or directory" in server_shell.execute("cat /etc/nope").output


def test_whoami_and_groups(server_shell):
    assert server_shell.execute("whoami").output == "player"
    assert server_shell.execute("groups").output == "player"


def test_sudo_is_required_for_privileged_commands(server_shell):
    result = server_shell.execute("apt update")
    assert result.output == "Permission denied (are you root?)"
    assert server_shell.state.system["pkg_index_updated"] is False


def test_unknown_flags_do_not_change_state(server_shell):
    result = server_shell.execute("ls --bogus")
    assert "unrecognized option" in result.output


def test_trailing_whitespace_is_tolerated(server_shell):
    assert server_shell.execute("pwd   ").output == "/home/player"


def test_checklist_lists_all_eleven_steps_with_progress(server_shell):
    output = server_shell.execute("checklist").output
    # Eleven steps plus a hint on exactly the first incomplete one.
    assert len(output.splitlines()) == 12
    assert "[x]" not in output
    assert "[ ]" in output
    assert "Step 1" in output
    assert "ssh -i ~/.ssh/id_ed25519 root@10.11.7.42" in output

    _connected_shell(server_shell)
    output = server_shell.execute("checklist").output
    assert "[x] Step 1" in output


def test_checklist_marks_completed_steps(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt upgrade -y")
    output = server_shell.execute("checklist").output
    assert "[x]" in output


def test_checklist_hints_only_the_next_incomplete_step(server_shell):
    _connected_shell(server_shell)
    output = server_shell.execute("checklist").output
    assert "Step 2" in output
    assert "apt update && apt upgrade" in output
    # A later step must not be hinted, so the player is not handed a walkthrough.
    assert "ufw default deny incoming" not in output


def test_the_challenge_can_be_completed_end_to_end(server_shell):
    server_shell._editor = _scripted_editor(server_shell)

    for command in FULL_PROVISIONING_SCRIPT:
        server_shell.execute(command)

    assert server_shell.state.session.get("pending_prompt") is None
    assert server_shell.state.complete is True
    assert [step.id for step in server_shell.state.steps() if not step.done] == []


def test_completion_survives_leaving_the_server(server_shell):
    server_shell._editor = _scripted_editor(server_shell)
    for command in FULL_PROVISIONING_SCRIPT:
        server_shell.execute(command)

    assert server_shell.state.complete is True

    server_shell.execute("exit")

    assert server_shell.state.complete is True


def test_help_states_the_mission_and_lists_commands(server_shell):
    output = server_shell.execute("help").output

    assert "maze-server" in output
    assert "neural link" in output
    assert "checklist" in output
    assert "ssh" in output
    assert "ufw" in output
    # The overview points the player at per-command topics.
    assert "help <" in output


def test_help_shows_the_next_expected_action(server_shell):
    # On the workstation the first incomplete step is connecting over ssh.
    output = server_shell.execute("help").output
    assert "ssh -i ~/.ssh/id_ed25519 root@10.11.7.42" in output

    _connected_shell(server_shell)
    output = server_shell.execute("help").output
    assert "apt update && apt upgrade" in output


def test_help_topic_shows_per_command_usage(server_shell):
    ssh = server_shell.execute("help ssh").output
    assert "ssh -i" in ssh
    assert "10.11.7.42" in ssh

    ufw = server_shell.execute("help ufw").output
    assert "ufw allow" in ufw


def test_help_alias_resolves_to_the_same_topic(server_shell):
    assert server_shell.execute("help apt-get").output == server_shell.execute("help apt").output
    assert server_shell.execute("help vim").output == server_shell.execute("help nano").output


def test_help_unknown_topic_is_rejected(server_shell):
    output = server_shell.execute("help frobnicate").output
    assert "No help" in output


def test_clear_requests_a_clear(server_shell):
    assert server_shell.execute("clear").clear_requested is True


def test_ls_all_and_long_format(server_shell):
    assert "sshd_config" in server_shell.execute("ls -l /etc/ssh").output
    assert ".ssh" in server_shell.execute("ls -a /home/player").output


def test_ls_reports_a_missing_path(server_shell):
    assert "No such file or directory" in server_shell.execute("ls /nope").output


def test_cat_missing_operand_and_directory(server_shell):
    assert server_shell.execute("cat").output == "cat: missing operand"
    assert server_shell.execute("cat /etc").output == "cat: /etc: Is a directory"
