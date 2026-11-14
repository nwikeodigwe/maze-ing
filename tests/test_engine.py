"""Integration tests for the engine, rooms and phases."""

import pytest


import src.rooms.lab_d2_002 as lab_d2_002
import src.rooms.teachers_room_4 as teachers_room_4
from src.rooms.teachers_room_4 import TeachersRoomFour
from src.room import Room
from src.rooms.front_desk import FrontDesk
from src.rooms.teachers_room_4 import SECRET_PATH
from src.utils.shell import ShellResult


def test_inventory_empty_and_populated(engine):
    engine.inventory()
    assert any("empty" in line for line in engine.outputs)

    engine.outputs.clear()
    engine.player["inventory"] = ["development_board", "obstacle_avoidance_module"]
    engine.inventory()

    text = "\n".join(engine.outputs)
    assert "ESP32 Development Board" in text
    assert "Obstacle Avoidance Module" in text
    assert "1/11" in text


def test_inventory_groups_duplicate_items(engine):
    engine.player["inventory"] = [
        "red_led", "red_led",
        "obstacle_avoidance_module", "obstacle_avoidance_module",
    ]
    engine.inventory()

    text = "\n".join(engine.outputs)
    assert "Red Light Emitting Diode x2" in text
    assert "Obstacle Avoidance Module x2" in text
    assert "2/11" in text


def test_status_screen_renders(engine):
    engine.flags["tr1_desk_unlocked"] = True
    engine.player["move"] = ["teachers_room_1"]
    engine.player["inventory"] = ["development_board"]

    engine.status()

    text = "\n".join(engine.outputs)
    assert "STATUS MENU" in text
    assert "Tester" in text
    assert "EXPLORATION" in text
    assert "desk unlocked" in text.lower()


def test_status_inventory_groups_duplicates(engine):
    engine.player["inventory"] = ["red_led", "red_led", "oled_display"]

    engine.status()

    text = "\n".join(engine.outputs)
    assert "Red Light Emitting Diode x2" in text
    assert "O.96 Inch OLED Display" in text


def test_helper_renders_rich_menu(engine, capsys):
    engine.helper()

    captured = capsys.readouterr().out
    assert "HELP MENU" in "\n".join(engine.outputs)
    assert "Movement" in captured


def test_inspect_dispatches_room_specific_targets(engine, monkeypatch):
    engine.inspect({"target": "terminal"})
    assert any("Exits" in line for line in engine.outputs)

    engine.player["current_room"] = "front_desk"
    engine.inspect({"target": "receptionist"})
    assert any("register" in line.lower() for line in engine.outputs)

    engine.player["current_room"] = "teachers_room_1"
    engine.inspect({"target": "desk"})
    assert any("Keypad hint" in line for line in engine.outputs)

    engine.player["current_room"] = "lab_d2_002"
    engine.inspect({"target": "workbench"})
    assert any("WORKBENCH" in line for line in engine.outputs)

    engine.player["current_room"] = "teachers_room_2"
    engine.inspect({"target": "whiteboard"})
    assert engine.flags["tr2_whiteboard_inspected"] is True

    engine.player["current_room"] = "teachers_room_4"
    engine.inspect({"target": "note"})
    assert any("note" in line.lower() for line in engine.outputs)

    called = []
    monkeypatch.setattr(engine, "inspect_computer", lambda: called.append(True))
    engine.inspect({"target": "computer"})
    assert called == [True]

    engine.inspect({"target": "nothing"})
    assert any("unavailable" in line for line in engine.outputs)


def test_use_desk_code_paths(engine):
    engine.player["current_room"] = "teachers_room_1"

    engine.use({"target": "wrong", "indirect": "desk"})
    assert "keycard_lvl1" not in engine.player["inventory"]

    engine.use({"target": "d2084", "indirect": "desk"})
    assert "keycard_lvl1" in engine.player["inventory"]
    assert engine.flags["tr1_desk_unlocked"] is True

    engine.use({"target": "d2084", "indirect": "desk"})
    assert any("already unlocked" in line for line in engine.outputs)

    engine.use({"target": "d2084", "indirect": "door"})
    assert any("Nothings happens" in line for line in engine.outputs)


def test_use_on_workbench_paths(engine):
    engine.player["current_room"] = "lab_d2_002"
    engine.player["inventory"] = ["obstacle_avoidance_module", "development_board"]

    engine.use({"target": "missing", "indirect": "workbench"})
    assert any("not a workbench component" in line for line in engine.outputs)

    engine.use({"target": "f_m_dupont_cable", "indirect": "workbench"})
    assert any("do not have" in line for line in engine.outputs)

    engine.use({"target": "development_board", "indirect": "workbench"})
    assert any("not a workbench component" in line for line in engine.outputs)

    engine.workbench["installed_parts"] = ["obstacle_avoidance_module"]
    engine.use({"target": "obstacle_avoidance_module", "indirect": "workbench"})
    assert any("already installed" in line for line in engine.outputs)

    engine.workbench["installed_parts"] = []
    engine.use({"target": "obstacle_avoidance_module", "indirect": "workbench"})
    assert "obstacle_avoidance_module" in engine.workbench["installed_parts"]
    assert "obstacle_avoidance_module" not in engine.player["inventory"]

    required = engine.workbench["required_parts"]
    engine.workbench["installed_parts"] = required[:-1]
    engine.player["inventory"] = [required[-1]]
    engine.use({"target": required[-1], "indirect": "workbench"})
    assert engine.workbench["is_ready"] is True
    assert engine.session["phase"] == "ASSEMBLY"


def test_use_elsewhere_reports_missing_or_useless(engine):
    engine.use({"target": "development_board", "indirect": "wall"})
    assert any("do not have" in line for line in engine.outputs)

    engine.player["inventory"] = ["development_board"]
    engine.use({"target": "development_board", "indirect": "wall"})
    assert any("cannot use" in line for line in engine.outputs)


def test_use_elsewhere_reports_unknown_item(engine):
    engine.player["inventory"] = ["blueprint"]

    engine.use({"target": "blueprint", "indirect": "wall"})

    assert any("cannot use" in line for line in engine.outputs)


def test_take_and_drop(engine):
    engine.take({"target": "development_board"})
    assert "development_board" in engine.player["inventory"]
    assert "development_board" not in engine.rooms["lobby"]["items"]

    engine.take({"target": "not_here"})
    assert any("no 'not_here' here" in line for line in engine.outputs)

    engine.drop({"target": "development_board"})
    assert "development_board" in engine.rooms["lobby"]["items"]

    engine.drop({"target": "not_an_item"})
    assert any("no item called" in line for line in engine.outputs)

    engine.drop({"target": "keycard_lvl1"})
    assert any("do not have" in line for line in engine.outputs)


def test_register_login_and_logout(engine):
    engine.player["current_room"] = "front_desk"

    engine.register({"target": "alice"})
    assert engine.player["name"] == "alice"
    assert engine.player["id"] == 1

    engine.register({"target": "alice"})
    assert any("already taken" in line for line in engine.outputs)

    engine.user.raise_on_create = ValueError("database down")
    engine.register({"target": "bob"})
    assert any("database down" in line for line in engine.outputs)

    engine.player["current_room"] = "lobby"
    engine.register({"target": "carol"})
    assert any("only register" in line for line in engine.outputs)

    engine.player["current_room"] = "front_desk"
    engine.login({"target": "alice"})
    assert engine.player["id"] == 1

    engine.login({"target": None})
    assert any("Please enter a name" in line for line in engine.outputs)

    engine.login({"target": "nobody"})
    assert any("does not exist" in line for line in engine.outputs)

    engine.logout()
    assert engine.player["name"] == "guest"
    assert engine.player["id"] is None

    engine.logout()
    assert any("not logged in" in line for line in engine.outputs)

    engine.player["current_room"] = "lobby"
    engine.logout()
    assert any("only complete" in line for line in engine.outputs)


def test_restart_keeps_identity_and_resets_clock(engine):
    engine.player["name"] = "alice"
    engine.player["id"] = 7
    engine.session["duration"]["value"] = "1:00:00"

    engine.restart()

    assert engine.player["name"] == "alice"
    assert engine.player["id"] == 7
    assert engine.session["duration"]["value"] == "00:00:00"
    assert engine.session["phase"] == "EXPLORATION"
    assert any("New game" in line for line in engine.outputs)


def test_scoreboard_empty_and_populated(engine):
    engine.render_scoreboard()
    assert any("No entries" in line for line in engine.outputs)

    engine.outputs.clear()
    engine.scoreboard.entries = [
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
    engine.user.users = [{"id": 1, "name": "alice"}]

    engine.render_scoreboard()

    text = "\n".join(engine.outputs)
    assert "Alice" in text
    assert "900" in text
    assert "Unknown (99)" in text


def test_shutdown_persists_and_stops(engine):
    engine.shutdown()

    assert engine.running is False
    assert engine.USER_STATE_PATH.exists()
    assert any("Goodbye" in line for line in engine.outputs)


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
def test_commands_dispatch(engine, monkeypatch, verb, method):
    called = []
    monkeypatch.setattr(
        engine, method, lambda *args, **kwargs: called.append(args)
    )

    engine.commands(verb, {"target": "x"})

    assert len(called) == 1


def test_commands_ignores_unknown(engine):
    engine.commands("UNKNOWN", {"target": "x"})
    assert engine.outputs == []


@pytest.mark.parametrize(
    ("phase", "method"),
    [
        ("EXPLORATION", "exploration"),
        ("ASSEMBLY", "assembly"),
        ("CHAT", "chat"),
        ("SOMETHING_ELSE", "exploration"),
    ],
)
def test_run_dispatches_phase_and_stops(engine, monkeypatch, phase, method):
    engine.session["phase"] = phase
    monkeypatch.setattr(engine, "auto", lambda: None)
    called = []

    def stop():
        called.append(method)
        engine.state.running = False

    monkeypatch.setattr(engine, method, stop)

    engine.run()

    assert called == [method]
    assert engine.player["current_room"] in engine.rooms


def test_exploration_phase_handles_commands_and_invalid_input(
    engine, monkeypatch
):
    commands = []
    monkeypatch.setattr(engine, "clear", lambda: None)
    monkeypatch.setattr(
        engine, "commands", lambda verb, details: commands.append((verb, details))
    )

    monkeypatch.setattr(engine, "prompt", lambda *args: "status")
    engine.exploration()
    assert commands[-1][0] == "status"

    monkeypatch.setattr(engine, "prompt", lambda *args: "zzz")
    engine.exploration()
    assert commands[-1][0] == "UNKNOWN"
    assert any("Invalid input" in line for line in engine.outputs)


def test_assembly_phase_intro_and_commands(engine, monkeypatch):
    monkeypatch.setattr(engine, "clear", lambda: None)
    rendered = []
    monkeypatch.setattr(
        engine, "render_workbench", lambda text=None: rendered.append(text)
    )
    engine.session["phases"]["assembly"]["activated"] = False

    engine.assembly()
    assert engine.session["phases"]["assembly"]["activated"] is True
    assert rendered

    commands = []
    activated = []
    monkeypatch.setattr(
        engine, "commands", lambda verb, details: commands.append(verb)
    )
    monkeypatch.setattr(engine, "activate", lambda: activated.append(True))
    monkeypatch.setattr(engine, "prompt", lambda *args: "activate")

    engine.assembly()
    assert commands == ["activate"]
    assert activated == [True]

    monkeypatch.setattr(engine, "prompt", lambda *args: "zzz")
    engine.assembly()
    assert any("Invalid input" in line for line in engine.outputs)


def test_chat_phase_intro_known_and_ai_input(engine, monkeypatch):
    monkeypatch.setattr(engine, "clear", lambda: None)
    rendered = []
    monkeypatch.setattr(engine, "render", lambda *args, **kwargs: rendered.append(args))
    engine.session["phases"]["chat"]["activated"] = False

    engine.chat()
    assert engine.session["phases"]["chat"]["activated"] is True
    assert rendered

    commands = []
    monkeypatch.setattr(
        engine, "commands", lambda verb, details: commands.append(verb)
    )
    engine.session["phases"]["chat"]["activated"] = True
    monkeypatch.setattr(engine, "prompt", lambda *args: "status")
    engine.chat()
    assert commands == ["status"]

    engine.player["current_room"] = "lab_d2_002"
    monkeypatch.setattr(engine, "prompt", lambda *args: "hello robot")
    engine.chat()
    assert engine.langchain.calls == ["hello robot"]

    engine.player["current_room"] = "lobby"
    engine.chat()
    assert any("Invalid input" in str(args) for args in rendered)


def test_lab_activate_success(engine, monkeypatch):
    answers = iter(["Tr0janH0rse!", "Robo"])
    monkeypatch.setattr(engine, "prompt", lambda *args: next(answers))
    monkeypatch.setattr(lab_d2_002.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(engine, "clear", lambda: None)
    engine.player["current_room"] = "lab_d2_001"
    engine.workbench["installed_parts"] = list(
        engine.workbench["required_parts"]
    )
    engine.flags["lab_server_provisioned"] = True

    engine.activate()

    assert engine.session["phase"] == "CHAT"
    assert engine.session["phases"]["chat"]["robot"]["name"] == "Robo"
    assert engine.scoreboard.created


def test_lab_activate_rejects_missing_parts_and_password(engine, monkeypatch):
    engine.player["current_room"] = "lab_d2_001"
    engine.workbench["installed_parts"] = []

    engine.activate()
    assert any("Assembly incomplete" in line for line in engine.outputs)

    engine.workbench["installed_parts"] = list(
        engine.workbench["required_parts"]
    )
    engine.flags["lab_server_provisioned"] = True
    monkeypatch.setattr(engine, "prompt", lambda *args: "wrong")
    monkeypatch.setattr(engine, "clear", lambda: None)
    engine.activate()
    assert engine.session["phase"] == "EXPLORATION"
    assert any("Invalid wifi" in line for line in engine.outputs)


def test_front_desk_room_inspect(engine):
    room = FrontDesk()
    room.state = engine.state
    room.render = lambda text=None: engine.outputs.append(text)

    room.inspect_receptionist()

    assert engine.outputs


def test_teachers_room_four_secret_key_and_shell(state, monkeypatch):
    room = TeachersRoomFour()
    room.state = state
    messages = []

    room._award_secret_key(messages.append)
    assert "secret_key" in state.player["inventory"]
    assert state.flags["tr4_secret_key_copied"] is True

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
    state, monkeypatch
):
    room = TeachersRoomFour()
    room.state = state
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

    monkeypatch.setattr(teachers_room_4, "loader", lambda **kwargs: None)
    monkeypatch.setattr(teachers_room_4.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(room, "clear", lambda: None)
    monkeypatch.setattr(teachers_room_4.console, "print", lambda *args, **kwargs: None)
    monkeypatch.setattr(room, "run_shell", lambda shell: messages.append("shell"))
    auto_calls = []
    renders = []
    monkeypatch.setattr(room, "auto", lambda: auto_calls.append(True))
    monkeypatch.setattr(room, "render", lambda *args, **kwargs: renders.append(True))

    room.inspect_computer()

    assert auto_calls == [True]
    assert renders == [True]
    assert state.session["duration"]["pause"] is False


def test_room_base_render_and_output(state, capsys):
    room = Room(state=state)
    state.player["current_room"] = "lobby"

    room.render(text="custom narrative")

    captured = capsys.readouterr().out
    assert "custom narrative" in captured
    assert "Exits:" in captured


def test_room_base_delegates_state_attributes(state):
    room = Room(state=state)

    assert room.player is state.player
    assert room.session is state.session
    assert callable(room.auto)


def test_room_base_missing_attribute_raises(state):
    room = Room(state=state)

    with pytest.raises(AttributeError):
        _ = room.does_not_exist


def test_footer_groups_duplicate_items(state, capsys):
    room = Room(state=state)
    state.player["current_room"] = "lobby"
    state.rooms["lobby"]["items"] = ["red_led", "red_led", "oled_display"]

    room.render()
    out = capsys.readouterr().out

    assert "Red Light Emitting Diode x2" in out
    assert out.count("Red Light Emitting Diode") == 1
    assert "O.96 Inch OLED Display" in out


def test_inspect_guide_pages_through_the_file(state, tmp_path, monkeypatch, capsys):
    guides = tmp_path / "guides"
    guides.mkdir()
    (guides / "lobby.txt").write_text(
        "\n".join(f"line {i}" for i in range(1, 10)), encoding="utf-8"
    )
    monkeypatch.setattr(state, "DATA_DIR", tmp_path)

    room = Room(state=state)
    state.player["current_room"] = "lobby"
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


def test_inspect_guide_quits_on_q(state, tmp_path, monkeypatch, capsys):
    guides = tmp_path / "guides"
    guides.mkdir()
    (guides / "lobby.txt").write_text(
        "\n".join(f"line {i}" for i in range(1, 10)), encoding="utf-8"
    )
    monkeypatch.setattr(state, "DATA_DIR", tmp_path)

    room = Room(state=state)
    state.player["current_room"] = "lobby"
    monkeypatch.setattr(room, "_read_page_key", lambda: "q")

    room.inspect_guide()

    out = capsys.readouterr().out
    assert "line 1" in out
    assert "line 5" not in out


def test_lab_d2_001_guide_is_non_empty_and_complete(state):
    guide = (
        state.DATA_DIR / "guides" / "lab_d2_001.txt"
    ).read_text(encoding="utf-8")

    assert guide.strip(), "lab_d2_001 guide file is empty"
    assert "inspect server" in guide
    assert "PermitRootLogin no" in guide
    assert "ufw allow 22/tcp" in guide
    assert "checklist" in guide
    assert "10.11.7.42" in guide
    assert "nginx" in guide


def test_lobby_guide_introduces_the_game(state):
    guide = (state.DATA_DIR / "guides" / "lobby.txt").read_text(
        encoding="utf-8"
    )

    assert guide.strip()
    assert "A-maze-ing Delft" in guide
    assert "register" in guide
    assert "maze-server" in guide


def test_front_desk_guide_jokes_and_encourages_trying(state):
    guide = (state.DATA_DIR / "guides" / "front_desk.txt").read_text(
        encoding="utf-8"
    )

    assert guide.strip()
    assert "register <name>" in guide
    assert "Knock knock" in guide
    assert "outside the box" in guide


def test_teachers_room_4_guide_navigates_the_computer(state):
    guide = (state.DATA_DIR / "guides" / "teachers_room_4.txt").read_text(
        encoding="utf-8"
    )

    assert guide.strip()
    assert "inspect computer" in guide
    assert "ls -a" in guide
    assert "super_secret_file.txt" in guide

def test_inspect_server_runs_the_terminal_session(engine, monkeypatch):
    engine.player["current_room"] = "lab_d2_001"
    engine.session["duration"]["value"] = "0:05:00"
    monkeypatch.setattr("src.rooms.lab_d2_001.loader", lambda **kwargs: None)
    commands = iter(["cd /etc", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(commands))

    engine.inspect_server()

    # The shell really ran and moved the shared server session.
    assert engine.state.server.session["cwd"] == "/etc"
    # The terminal session is not charged to the player, and the clock resumes.
    assert engine.session["duration"]["value"] == "0:05:00"
    assert engine.session["duration"]["pause"] is False
    # The session is persisted, so leaving the lab cannot lose progress.
    import json

    payload = json.loads(
        engine.state.USER_STATE_PATH.read_text(encoding="utf-8")
    )
    assert payload["server"]["session"]["cwd"] == "/etc"

def test_award_sets_the_flag_and_grants_the_certificate(engine):
    engine._award_provisioning_certificate()

    assert engine.flags["lab_server_provisioned"] is True
    assert "server_provisioning_certificate" in engine.player["inventory"]


def test_award_does_not_duplicate_the_certificate(engine):
    engine._award_provisioning_certificate()
    engine._award_provisioning_certificate()

    assert engine.player["inventory"].count("server_provisioning_certificate") == 1


def test_completing_the_challenge_awards_the_certificate(engine, monkeypatch):
    engine.player["current_room"] = "lab_d2_001"
    monkeypatch.setattr("src.rooms.lab_d2_001.loader", lambda **kwargs: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "exit")
    monkeypatch.setattr(
        type(engine.server), "complete", property(lambda self: True)
    )

    engine.inspect_server()

    assert engine.flags["lab_server_provisioned"] is True
    assert "server_provisioning_certificate" in engine.player["inventory"]


def test_activate_refuses_until_the_server_is_provisioned(engine, monkeypatch):
    engine.player["current_room"] = "lab_d2_002"
    engine.workbench["installed_parts"] = list(engine.workbench["required_parts"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "Tr0janH0rse!")

    engine.activate()

    assert engine.session["phase"] == "EXPLORATION"
    assert any("provisioned" in line for line in engine.outputs)

def test_teachers_room_four_terminal_does_not_charge_the_clock(state, monkeypatch):
    room = TeachersRoomFour()
    room.state = state
    state.session["duration"]["value"] = "0:05:00"

    class SilentConsole:
        def print(self, *args, **kwargs):
            pass

    monkeypatch.setattr(teachers_room_4, "console", SilentConsole())
    monkeypatch.setattr(teachers_room_4.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(teachers_room_4, "loader", lambda **kwargs: None)
    monkeypatch.setattr(room, "run_shell", lambda shell: None)

    room.inspect_computer()

    assert state.session["duration"]["value"] == "0:05:00"
    assert state.session["duration"]["pause"] is False
