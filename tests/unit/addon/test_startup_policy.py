"""Behavioral regressions for FreeCAD startup and timer ownership."""

import importlib.util
import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

ADDON = Path(__file__).resolve().parents[3] / "freecad" / "RobustMCPBridge"
spec = importlib.util.spec_from_file_location(
    "startup_policy_under_test", ADDON / "freecad_mcp_bridge" / "startup_policy.py"
)
assert spec is not None and spec.loader is not None
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


@pytest.mark.parametrize(
    ("arguments", "batch"),
    [
        ([], False),
        (["--console"], False),
        (["-u", "config.xml", "--system-cfg=system.xml"], False),
        (["-M/path/to/modules", "-l"], False),
        (["model.FCStd"], True),
        (["script.py"], True),
        (["--", "script.py"], True),
        (["-t", "0"], True),
        (["--run-test=0"], True),
        (["-r0"], True),
        (["--run-open", "0"], True),
        (["--response-file", "opts.txt"], True),
        (["@opts.txt"], True),
        (["--get-config", "x"], True),
        (["--unknown"], True),
        (["-u"], True),
    ],
)
def test_batch_classification(arguments: list[str], batch: bool) -> None:
    """Explicitly distinguish interactive options from commands and files."""
    assert policy.is_batch_invocation(arguments) is batch


@pytest.mark.parametrize(
    ("executable", "expected"),
    [
        ("/opt/bin/freecadcmd", True),
        ("freecadcmd.exe", True),
        ("/opt/bin/freecad", False),
        ("/opt/bin/cmd-freecad", False),
        ("", False),
    ],
)
def test_only_exact_console_executables(executable: str, expected: bool) -> None:
    """Unrelated binaries and partial matches must not authorize headless mode."""
    assert policy.is_console_executable(executable) is expected


@pytest.mark.parametrize(
    ("executable", "arguments", "expected"),
    [
        ("freecadcmd", [], True),
        ("freecad", ["--console"], True),
        ("freecad", ["-c"], True),
        ("freecad.exe", ["--console"], True),
        ("other", ["--console"], False),
        ("freecad", [], False),
        ("freecad", ["-u", "--console"], False),
        ("freecad", ["--response-file", "--console"], False),
        ("freecad", ["--get-config", "--console"], False),
        ("freecad", ["--run-test", "--console"], False),
        ("freecad", ["--pass", "--console"], False),
        ("freecad", ["--unknown", "--console"], False),
        ("freecad", ["document.FCStd", "--console"], False),
        ("freecad", ["--run-test", "0", "--console"], True),
        ("freecad", ["--", "--console"], False),
    ],
)
def test_explicit_console_mode(
    executable: str, arguments: list[str], expected: bool
) -> None:
    """Accept console mode only for FreeCAD and actual option arguments."""
    assert policy.is_console_invocation(executable, arguments) is expected


def test_cleanup_only_touches_owned_timers_on_their_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A foreign-thread timer and an unrelated timer remain untouched."""
    monkeypatch.setenv("FREECAD_MCP_TESTING", "1")
    monkeypatch.syspath_prepend(str(ADDON))
    freecad = ModuleType("FreeCAD")
    freecad.Console = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "preferences", MagicMock())
    import atexit

    monkeypatch.setattr(atexit, "register", lambda *_args: None)
    namespace = runpy.run_path(
        str(ADDON / "__init__.py"), run_name="startup_under_test"
    )
    cleanup = namespace["_release_startup_timers"]
    state = cleanup.__globals__
    owner = object()
    qtcore = MagicMock()
    qtcore.QThread.currentThread.return_value = owner
    owned = MagicMock()
    owned.thread.return_value = owner
    foreign = MagicMock()
    foreign.thread.return_value = object()
    unrelated = MagicMock()
    waiter = SimpleNamespace(_check_timer=owned, _defer_timer=foreign)
    state["_auto_start_timer"] = None
    state["_gui_waiter"] = waiter
    from freecad_mcp_bridge import qt_compat, server

    delete = MagicMock()
    monkeypatch.setattr(qt_compat, "load_qt_core", lambda: qtcore)
    monkeypatch.setattr(server, "_get_shiboken_delete", lambda: delete)

    cleanup()

    owned.stop.assert_called_once()
    delete.assert_called_once_with(owned)
    foreign.stop.assert_not_called()
    unrelated.stop.assert_not_called()
    assert waiter._check_timer is None
    assert waiter._defer_timer is foreign


@pytest.mark.parametrize(
    ("gui_enabled", "headless_enabled", "batch_enabled", "arguments", "expected"),
    [
        (False, False, False, [], False),
        (False, True, False, [], True),
        (True, False, False, [], False),
        (False, True, False, ["script.py"], False),
        (False, True, True, ["script.py"], True),
        (False, True, False, ["--run-test", "0"], False),
    ],
)
def test_headless_preference_and_batch_gates(
    monkeypatch: pytest.MonkeyPatch,
    gui_enabled: bool,
    headless_enabled: bool,
    batch_enabled: bool,
    arguments: list[str],
    expected: bool,
) -> None:
    """Headless and GUI preferences are independent and batch is opt-in."""
    import atexit

    monkeypatch.delenv("FREECAD_MCP_TESTING", raising=False)
    monkeypatch.syspath_prepend(str(ADDON))
    monkeypatch.setattr(sys, "executable", "/opt/freecad/bin/freecadcmd")
    monkeypatch.setattr(sys, "argv", ["freecadcmd", *arguments])
    monkeypatch.setattr(atexit, "register", lambda *_args: None)
    freecad = ModuleType("FreeCAD")
    freecad.GuiUp = False  # type: ignore[attr-defined]
    freecad.Console = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    preferences = MagicMock()
    preferences.get_auto_start.return_value = gui_enabled
    preferences.get_auto_start_headless.return_value = headless_enabled
    preferences.get_auto_start_headless_batch.return_value = batch_enabled
    monkeypatch.setitem(sys.modules, "preferences", preferences)
    commands = MagicMock()
    commands._mcp_plugin = None
    monkeypatch.setitem(sys.modules, "commands", commands)
    from freecad_mcp_bridge import qt_compat, server

    qtcore = MagicMock()
    qtcore.QCoreApplication.instance.return_value = None
    monkeypatch.setattr(
        qt_compat,
        "load_qt_core_widgets",
        lambda: (qtcore, SimpleNamespace(QApplication=type("QApplication", (), {}))),
    )
    plugin = MagicMock()
    monkeypatch.setattr(server, "FreecadMCPPlugin", MagicMock(return_value=plugin))

    runpy.run_path(str(ADDON / "__init__.py"), run_name="startup_under_test")

    assert plugin.start.called is expected


@pytest.mark.parametrize("gui_enabled", [False, True])
def test_gui_preference_remains_independent(
    monkeypatch: pytest.MonkeyPatch, gui_enabled: bool
) -> None:
    """Headless auto-start must not override the GUI preference."""
    import atexit

    monkeypatch.delenv("FREECAD_MCP_TESTING", raising=False)
    monkeypatch.syspath_prepend(str(ADDON))
    monkeypatch.setattr(sys, "executable", "/opt/freecad/bin/freecad")
    monkeypatch.setattr(sys, "argv", ["freecad"])
    monkeypatch.setattr(atexit, "register", lambda *_args: None)
    freecad = ModuleType("FreeCAD")
    freecad.GuiUp = True  # type: ignore[attr-defined]
    freecad.Console = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    preferences = MagicMock()
    preferences.get_auto_start.return_value = gui_enabled
    preferences.get_auto_start_headless.return_value = True
    monkeypatch.setitem(sys.modules, "preferences", preferences)
    from freecad_mcp_bridge import qt_compat

    qtcore = MagicMock()
    qtcore.QCoreApplication.instance.return_value = None
    monkeypatch.setattr(
        qt_compat,
        "load_qt_core_widgets",
        lambda: (qtcore, SimpleNamespace(QApplication=type("QApplication", (), {}))),
    )
    runpy.run_path(str(ADDON / "__init__.py"), run_name="startup_under_test")
    assert qtcore.QTimer.called is gui_enabled
