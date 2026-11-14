"""Integration tests for the engine, rooms and phases."""

import pytest

import src.rooms.lab_d2_002 as lab_oop
import src.rooms.teachers_room_4 as tr4_oop
import src.room as room_oop

from src.rooms.front_desk import FrontDesk
from src.rooms.teachers_room_4 import SECRET_PATH, TeachersRoomFour
from src.utils.shell import ShellResult


def test_inventory_empty_and_populated(oop_engine):
    oop_engine.inventory()
    assert any("empty" in line for line in oop_engine.outputs)

    oop_engine.outputs.clear()
    oop_engine.player["inventory"] = ["development_board", "obstacle_avoidance_module"]
    oop_engine.inventory()

    text = "\n".join(oop_engine.outputs)
    assert "ESP32 Development Board" in text
    assert "Obstacle Avoidance Module" in text
    assert "1/11" in text


def test_inventory_groups_duplicate_items(oop_engine):
    oop_engine.player["inventory"] = [
        "red_led", "red_led",
        "obstacle_avoidance_module", "obstacle_avoidance_module",
    ]
    oop_engine.inventory()

    text = "\n".join(oop_engine.outputs)
    assert "Red Light Emitting Diode x2" in text
    assert "Obstacle Avoidance Module x2" in text
    assert "2/11" in text


def test_status_screen_renders(oop_engine):
    oop_engine.flags["tr1_desk_unlocked"] = True
    oop_engine.player["move"] = ["teachers_room_1"]
    oop_engine.player["inventory"] = ["development_board"]

    oop_engine.status()

    text = "\n".join(oop_engine.outputs)
    assert "STATUS MENU" in text
    assert "Tester" in text
    assert "EXPLORATION" in text
    assert "desk unlocked" in text.lower()


def test_status_inventory_groups_duplicates(oop_engine):
    oop_engine.player["inventory"] = ["red_led", "red_led", "oled_display"]

    oop_engine.status()

    text = "\n".join(oop_engine.outputs)
    assert "Red Light Emitting Diode x2" in text
    assert "O.96 Inch OLED Display" in text


def test_helper_renders_rich_menu(oop_engine, capsys):
    oop_engine.helper()

    captured = capsys.readouterr().out
    assert "HELP MENU" in "\n".join(oop_engine.outputs)
    assert "Movement" in captured


def test_inspect_dispatches_room_specific_targets(oop_engine, monkeypatch):
    oop_engine.inspect({"target": "terminal"})
    assert any("Exits" in line for line in oop_engine.outputs)

    oop_engine.player["current_room"] = "front_desk"
    oop_engine.inspect({"target": "receptionist"})
    assert any("receptionist" in line.lower() for line in oop_engine.outputs)

    oop_engine.player["current_room"] = "teachers_room_1"
    oop_engine.inspect({"target": "desk"})
    assert any("Keypad hint" in line for line in oop_engine.outputs)

    oop_engine.player["current_room"] = "lab_d2_002"
    oop_engine.inspect({"target": "workbench"})
    assert any("WORKBENCH" in line for line in oop_engine.outputs)

    oop_engine.player["current_room"] = "teachers_room_2"
    oop_engine.inspect({"target": "whiteboard"})
    assert oop_engine.flags["tr2_whiteboard_inspected"] is True

    oop_engine.player["current_room"] = "teachers_room_4"
    oop_engine.inspect({"target": "note"})
    assert any("note" in line.lower() for line in oop_engine.outputs)

    called = []
    monkeypatch.setattr(oop_engine, "inspect_computer", lambda: called.append(True))
    oop_engine.inspect({"target": "computer"})
    assert called == [True]

    oop_engine.inspect({"target": "nothing"})
    assert any("unavailable" in line for line in oop_engine.outputs)


def test_use_desk_code_paths(oop_engine):
    oop_engine.player["current_room"] = "teachers_room_1"

    oop_engine.use({"target": "wrong", "indirect": "desk"})
    assert "keycard_lvl1" not in oop_engine.player["inventory"]

    oop_engine.use({"target": "d2084", "indirect": "desk"})
    assert "keycard_lvl1" in oop_engine.player["inventory"]
    assert oop_engine.flags["tr1_desk_unlocked"] is True

    oop_engine.use({"target": "d2084", "indirect": "desk"})
    assert any("already unlocked" in line for line in oop_engine.outputs)

    oop_engine.use({"target": "d2084", "indirect": "door"})
    assert any("Nothings happens" in line for line in oop_engine.outputs)


def test_use_on_workbench_paths(oop_engine):
    oop_engine.player["current_room"] = "lab_d2_002"
    oop_engine.player["inventory"] = ["obstacle_avoidance_module", "development_board"]

    oop_engine.use({"target": "missing", "indirect": "workbench"})
    assert any("not a workbench component" in line for line in oop_engine.outputs)

    oop_engine.use({"target": "f_m_dupont_cable", "indirect": "workbench"})
    assert any("do not have" in line for line in oop_engine.outputs)

    oop_engine.use({"target": "development_board", "indirect": "workbench"})
    assert any("not a workbench component" in line for line in oop_engine.outputs)

    oop_engine.workbench["installed_parts"] = ["obstacle_avoidance_module"]
    oop_engine.use({"target": "obstacle_avoidance_module", "indirect": "workbench"})
    assert any("already installed" in line for line in oop_engine.outputs)

    oop_engine.workbench["installed_parts"] = []
    oop_engine.use({"target": "obstacle_avoidance_module", "indirect": "workbench"})
    assert "obstacle_avoidance_module" in oop_engine.workbench["installed_parts"]
    assert "obstacle_avoidance_module" not in oop_engine.player["inventory"]

    required = oop_engine.workbench["required_parts"]
    oop_engine.workbench["installed_parts"] = required[:-1]
    oop_engine.player["inventory"] = [required[-1]]
    oop_engine.use({"target": required[-1], "indirect": "workbench"})
    assert oop_engine.workbench["is_ready"] is True
    assert oop_engine.session["phase"] == "ASSEMBLY"


def test_use_elsewhere_reports_missing_or_useless(oop_engine):
    oop_engine.use({"target": "development_board", "indirect": "wall"})
    assert any("do not have" in line for line in oop_engine.outputs)

    oop_engine.player["inventory"] = ["development_board"]
    oop_engine.use({"target": "development_board", "indirect": "wall"})
    assert any("cannot use" in line for line in oop_engine.outputs)


def test_use_elsewhere_reports_unknown_item(oop_engine):
    oop_engine.player["inventory"] = ["blueprint"]

    oop_engine.use({"target": "blueprint", "indirect": "wall"})

    assert any("cannot use" in line for line in oop_engine.outputs)


def test_take_and_drop(oop_engine):
    oop_engine.take({"target": "development_board"})
    assert "development_board" in oop_engine.player["inventory"]
    assert "development_board" not in oop_engine.rooms["lobby"]["items"]

    oop_engine.take({"target": "not_here"})
    assert any("no 'not_here' here" in line for line in oop_engine.outputs)

    oop_engine.drop({"target": "development_board"})
    assert "development_board" in oop_engine.rooms["lobby"]["items"]

    oop_engine.drop({"target": "not_an_item"})
    assert any("no item called" in line for line in oop_engine.outputs)

    oop_engine.drop({"target": "keycard_lvl1"})
    assert any("do not have" in line for line in oop_engine.outputs)


def test_register_login_and_logout(oop_engine):
    oop_engine.player["current_room"] = "front_desk"

    oop_engine.register({"target": "alice"})
    assert oop_engine.player["name"] == "alice"
    assert oop_engine.player["id"] == 1

    oop_engine.register({"target": "alice"})
    assert any("already taken" in line for line in oop_engine.outputs)

    oop_engine.user.raise_on_create = ValueError("database down")
    oop_engine.register({"target": "bob"})
    assert any("database down" in line for line in oop_engine.outputs)

    oop_engine.player["current_room"] = "lobby"
    oop_engine.register({"target": "carol"})
    assert any("only register" in line for line in oop_engine.outputs)

    oop_engine.player["current_room"] = "front_desk"
    oop_engine.login({"target": "alice"})
    assert oop_engine.player["id"] == 1

    oop_engine.login({"target": None})
    assert any("Please enter a name" in line for line in oop_engine.outputs)

    oop_engine.login({"target": "nobody"})
    assert any("does not exist" in line for line in oop_engine.outputs)

    oop_engine.logout()
    assert oop_engine.player["name"] == "guest"
    assert oop_engine.player["id"] is None

    oop_engine.logout()
    assert any("not logged in" in line for line in oop_engine.outputs)

    oop_engine.player["current_room"] = "lobby"
    oop_engine.logout()
    assert any("only complete" in line for line in oop_engine.outputs)


def test_restart_keeps_identity_and_resets_clock(oop_engine):
    oop_engine.player["name"] = "alice"
    oop_engine.player["id"] = 7
    oop_engine.session["duration"]["value"] = "1:00:00"

    oop_engine.restart()

    assert oop_engine.player["name"] == "alice"
    assert oop_engine.player["id"] == 7
    assert oop_engine.session["duration"]["value"] == "00:00:00"
    assert oop_engine.session["phase"] == "EXPLORATION"
    assert any("New game" in line for line in oop_engine.outputs)


def test_scoreboard_empty_and_populated(oop_engine):
    oop_engine.render_scoreboard()
    assert any("No entries" in line for line in oop_engine.outputs)

    oop_engine.outputs.clear()
    oop_engine.scoreboard.entries = [
        {
            "user_id": 1,
            "score": 900,
            "avg_room_time": "0:01:00",
            "exploration_time": "0:10:00",
            "assembly_time": "0:02:00",
        },
        {
            "user_id": 99,
            "score": 800,
            "avg_room_time": "0:02:00",
            "exploration_time": "0:12:00",
            "assembly_time": "0:03:00",
        },
    ]
    oop_engine.user.users = [{"id": 1, "name": "alice"}]

    oop_engine.render_scoreboard()

    text = "\n".join(oop_engine.outputs)
    assert "Alice" in text
    assert "900" in text
    assert "Unknown (99)" in text


def test_shutdown_persists_and_stops(oop_engine):
    oop_engine.shutdown()

    assert oop_engine.running is False
    assert oop_engine.USER_STATE_PATH.exists()
    assert any("Goodbye" in line for line in oop_engine.outputs)


@pytest.mark.parametrize(
    ("verb", "method"),
    [
        ("quit", "shutdown"),
        ("restart", "restart"),
        ("help", "helper"),
        ("scoreboard", "render_scoreboard"),
        ("status", "status"),
        ("inventory", "inventory"),
        ("use", "use"),
        ("register", "register"),
        ("login", "login"),
        ("logout", "logout"),
        ("save", "save"),
        ("saves", "saves"),
        ("load", "load"),
        ("inspect", "inspect"),
        ("look", "render"),
        ("take", "take"),
        ("drop", "drop"),
        ("go", "navigate"),
    ],
)
def test_commands_dispatch(oop_engine, monkeypatch, verb, method):
    called = []
    monkeypatch.setattr(
        oop_engine, method, lambda *args, **kwargs: called.append(args)
    )

    oop_engine.commands(verb, {"target": "x"})

    assert len(called) == 1


def test_commands_ignores_unknown(oop_engine):
    oop_engine.commands("UNKNOWN", {"target": "x"})
    assert oop_engine.outputs == []


@pytest.mark.parametrize(
    ("phase", "method"),
    [
        ("EXPLORATION", "exploration"),
        ("ASSEMBLY", "assembly"),
        ("CHAT", "chat"),
        ("SOMETHING_ELSE", "exploration"),
    ],
)
def test_run_dispatches_phase_and_stops(oop_engine, monkeypatch, phase, method):
    oop_engine.session["phase"] = phase
    monkeypatch.setattr(oop_engine, "auto", lambda: None)
    called = []

    def stop():
        called.append(method)
        oop_engine.state.running = False

    monkeypatch.setattr(oop_engine, method, stop)

    oop_engine.run()

    assert called == [method]
    assert oop_engine.player["current_room"] in oop_engine.rooms


def test_exploration_phase_handles_commands_and_invalid_input(
    oop_engine, monkeypatch
):
    commands = []
    monkeypatch.setattr(oop_engine, "clear", lambda: None)
    monkeypatch.setattr(
        oop_engine, "commands", lambda verb, details: commands.append((verb, details))
    )

    monkeypatch.setattr(oop_engine, "prompt", lambda *args: "status")
    oop_engine.exploration()
    assert commands[-1][0] == "status"

    monkeypatch.setattr(oop_engine, "prompt", lambda *args: "zzz")
    oop_engine.exploration()
    assert commands[-1][0] == "UNKNOWN"
    assert any("Invalid input" in line for line in oop_engine.outputs)


def test_assembly_phase_intro_and_commands(oop_engine, monkeypatch):
    monkeypatch.setattr(oop_engine, "clear", lambda: None)
    rendered = []
    monkeypatch.setattr(
        oop_engine, "render_workbench", lambda text=None: rendered.append(text)
    )
    oop_engine.session["phases"]["assembly"]["activated"] = False

    oop_engine.assembly()
    assert oop_engine.session["phases"]["assembly"]["activated"] is True
    assert rendered

    commands = []
    activated = []
    monkeypatch.setattr(
        oop_engine, "commands", lambda verb, details: commands.append(verb)
    )
    monkeypatch.setattr(oop_engine, "activate", lambda: activated.append(True))
    monkeypatch.setattr(oop_engine, "prompt", lambda *args: "activate")

    oop_engine.assembly()
    assert commands == ["activate"]
    assert activated == [True]

    monkeypatch.setattr(oop_engine, "prompt", lambda *args: "zzz")
    oop_engine.assembly()
    assert any("Invalid input" in line for line in oop_engine.outputs)


def test_chat_phase_intro_known_and_ai_input(oop_engine, monkeypatch):
    monkeypatch.setattr(oop_engine, "clear", lambda: None)
    rendered = []
    monkeypatch.setattr(oop_engine, "render", lambda *args, **kwargs: rendered.append(args))
    oop_engine.session["phases"]["chat"]["activated"] = False

    oop_engine.chat()
    assert oop_engine.session["phases"]["chat"]["activated"] is True
    assert rendered

    commands = []
    monkeypatch.setattr(
        oop_engine, "commands", lambda verb, details: commands.append(verb)
    )
    oop_engine.session["phases"]["chat"]["activated"] = True
    monkeypatch.setattr(oop_engine, "prompt", lambda *args: "status")
    oop_engine.chat()
    assert commands == ["status"]

    oop_engine.player["current_room"] = "lab_d2_002"
    monkeypatch.setattr(oop_engine, "prompt", lambda *args: "hello robot")
    oop_engine.chat()
    assert oop_engine.langchain.calls == ["hello robot"]

    oop_engine.player["current_room"] = "lobby"
    oop_engine.chat()
    assert any("Invalid input" in str(args) for args in rendered)


def test_lab_activate_success(oop_engine, monkeypatch):
    answers = iter(["Tr0janH0rse!", "Robo"])
    monkeypatch.setattr(oop_engine, "prompt", lambda *args: next(answers))
    monkeypatch.setattr(lab_oop.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(oop_engine, "clear", lambda: None)
    oop_engine.player["current_room"] = "lab_d2_001"
    oop_engine.workbench["installed_parts"] = list(
        oop_engine.workbench["required_parts"]
    )

    oop_engine.activate()

    assert oop_engine.session["phase"] == "CHAT"
    assert oop_engine.session["phases"]["chat"]["robot"]["name"] == "Robo"
    assert oop_engine.scoreboard.created


def test_lab_activate_rejects_missing_parts_and_password(oop_engine, monkeypatch):
    oop_engine.player["current_room"] = "lab_d2_001"
    oop_engine.workbench["installed_parts"] = []

    oop_engine.activate()
    assert any("Assembly incomplete" in line for line in oop_engine.outputs)

    oop_engine.workbench["installed_parts"] = list(
        oop_engine.workbench["required_parts"]
    )
    monkeypatch.setattr(oop_engine, "prompt", lambda *args: "wrong")
    monkeypatch.setattr(oop_engine, "clear", lambda: None)
    oop_engine.activate()
    assert oop_engine.session["phase"] == "EXPLORATION"
    assert any("Invalid wifi" in line for line in oop_engine.outputs)


def test_front_desk_room_inspect(oop_engine):
    room = FrontDesk()
    room.state = oop_engine.state
    room.render = lambda text=None: oop_engine.outputs.append(text)

    room.inspect_receptionist()

    assert oop_engine.outputs


def test_teachers_room_four_secret_key_and_shell(oop_state, monkeypatch):
    room = TeachersRoomFour()
    room.state = oop_state
    messages = []

    room._award_secret_key(messages.append)
    assert "secret_key" in oop_state.player["inventory"]
    assert oop_state.flags["tr4_secret_key_copied"] is True

    room._award_secret_key(messages.append)
    assert any("already in your inventory" in message for message in messages)

    class FakeShell:
        user = "teacher"
        hostname = "teacher-pc"
        display_cwd = "~"

        def __init__(self):
            self.results = iter(
                [
                    ShellResult(
                        output="secret",
                        clear_requested=True,
                        read_paths=(SECRET_PATH,),
                    ),
                    ShellResult(exit_requested=True),
                ]
            )

        def execute(self, raw):
            return next(self.results)

    cleared = []
    inputs = iter(["cat secret", "exit"])
    room.clear = lambda: cleared.append(True)
    room.run_shell(
        FakeShell(),
        read_input=lambda prompt=None: next(inputs),
        write_output=messages.append,
    )
    assert cleared == [True]


def test_teachers_room_four_handles_eof_and_computer(
    oop_state, monkeypatch
):
    room = TeachersRoomFour()
    room.state = oop_state
    messages = []

    def eof(prompt=None):
        raise EOFError

    class PromptShell:
        user = "teacher"
        hostname = "teacher-pc"
        display_cwd = "~"

    room.run_shell(
        PromptShell(),
        read_input=eof,
        write_output=messages.append,
    )
    assert messages

    monkeypatch.setattr(tr4_oop, "loader", lambda **kwargs: None)
    monkeypatch.setattr(tr4_oop.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(room, "clear", lambda: None)
    monkeypatch.setattr(tr4_oop.console, "print", lambda *args, **kwargs: None)
    monkeypatch.setattr(room, "run_shell", lambda shell: messages.append("shell"))
    auto_calls = []
    renders = []
    monkeypatch.setattr(room, "auto", lambda: auto_calls.append(True))
    monkeypatch.setattr(room, "render", lambda *args, **kwargs: renders.append(True))

    room.inspect_computer()

    assert auto_calls == [True]
    assert renders == [True]
    assert oop_state.session["duration"]["pause"] is False


def test_room_base_render_and_output(oop_state, capsys):
    room = room_oop.Room(state=oop_state)
    oop_state.player["current_room"] = "lobby"

    room.render(text="custom narrative")

    captured = capsys.readouterr().out
    assert "custom narrative" in captured
    assert "Exits:" in captured


def test_room_base_delegates_state_attributes(oop_state):
    room = room_oop.Room(state=oop_state)

    assert room.player is oop_state.player
    assert room.session is oop_state.session
    assert callable(room.auto)


def test_room_base_missing_attribute_raises(oop_state):
    room = room_oop.Room(state=oop_state)

    with pytest.raises(AttributeError):
        _ = room.does_not_exist


def test_footer_groups_duplicate_items(oop_state, capsys):
    room = room_oop.Room(state=oop_state)
    oop_state.player["current_room"] = "lobby"
    oop_state.rooms["lobby"]["items"] = ["red_led", "red_led", "oled_display"]

    room.render()
    out = capsys.readouterr().out

    assert "Red Light Emitting Diode x2" in out
    assert out.count("Red Light Emitting Diode") == 1
    assert "O.96 Inch OLED Display" in out


def test_inspect_guide_pages_through_the_file(oop_state, tmp_path, monkeypatch, capsys):
    guides = tmp_path / "guides"
    guides.mkdir()
    (guides / "lobby.txt").write_text(
        "\n".join(f"line {i}" for i in range(1, 10)), encoding="utf-8"
    )
    monkeypatch.setattr(oop_state, "DATA_DIR", tmp_path)

    room = room_oop.Room(state=oop_state)
    oop_state.player["current_room"] = "lobby"
    keys = []

    def fake_key():
        keys.append("")
        return ""

    monkeypatch.setattr(room, "_read_page_key", fake_key)
    room.inspect_guide()

    out = capsys.readouterr().out
    assert "line 1" in out
    assert "line 9" in out
    assert len(keys) == 2
    # The ":" prompt is erased instead of being left in the terminal.
    assert "\r" in out


def test_inspect_guide_quits_on_q(oop_state, tmp_path, monkeypatch, capsys):
    guides = tmp_path / "guides"
    guides.mkdir()
    (guides / "lobby.txt").write_text(
        "\n".join(f"line {i}" for i in range(1, 10)), encoding="utf-8"
    )
    monkeypatch.setattr(oop_state, "DATA_DIR", tmp_path)

    room = room_oop.Room(state=oop_state)
    oop_state.player["current_room"] = "lobby"
    monkeypatch.setattr(room, "_read_page_key", lambda: "q")

    room.inspect_guide()

    out = capsys.readouterr().out
    assert "line 1" in out
    assert "line 5" not in out

def test_inspect_server_runs_the_terminal_session(oop_engine, monkeypatch):
    oop_engine.player["current_room"] = "lab_d2_001"
    oop_engine.session["duration"]["value"] = "0:05:00"
    monkeypatch.setattr("src.rooms.lab_d2_001.loader", lambda **kwargs: None)
    commands = iter(["cd /etc", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(commands))

    oop_engine.inspect_server()

    # The shell really ran and moved the shared server session.
    assert oop_engine.state.server.session["cwd"] == "/etc"
    # The terminal session is not charged to the player, and the clock resumes.
    assert oop_engine.session["duration"]["value"] == "0:05:00"
    assert oop_engine.session["duration"]["pause"] is False
