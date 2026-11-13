"""Verify default-deny review behavior without requiring a Qt GUI."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def modules(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType, ModuleType, MagicMock]:
    """Load the modules in an isolated package with a minimal Qt stand-in."""
    base = Path(__file__).parents[3] / "freecad/RobustMCPBridge/freecad_mcp_bridge"
    package = ModuleType("review_dialog_test")
    package.__path__ = [str(base)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    qtwidgets = MagicMock()
    qtcore = MagicMock()
    qtcore.QThread.currentThread.return_value = "main"
    qtwidgets.QApplication.instance.return_value.thread.return_value = "main"
    qtwidgets.QDialog.Accepted = 1
    editor = qtwidgets.QPlainTextEdit.return_value
    editor.setPlainText.side_effect = lambda value: setattr(
        editor.toPlainText, "return_value", value
    )
    qt = ModuleType("review_dialog_test.qt_compat")
    qt.load_qt_core_widgets = lambda: (qtcore, qtwidgets)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, qt.__name__, qt)

    def load(name: str) -> ModuleType:
        spec = importlib.util.spec_from_file_location(
            f"review_dialog_test.{name}", base / f"{name}.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        return module

    return load("approval"), load("review_dialog"), qtwidgets


def test_dialog_displays_exact_code_and_approval_is_single_use(modules: tuple) -> None:
    """Only an affirmative dialog result approves the exact request."""
    approval, review, widgets = modules
    request = approval.ApprovalRequest(
        approval.ApprovalPayload("execute_python", b"x = 1\nprint(x)"), 30
    )
    dialog = review.create_review_dialog(request)
    widgets.QPlainTextEdit.return_value.setPlainText.assert_called_once_with(
        "x = 1\nprint(x)"
    )
    handler = dialog.finished.connect.call_args.args[0]
    assert request.consume() is None
    handler(1)
    assert request.consume() is request.payload
    handler(1)
    assert request.consume() is None


@pytest.mark.parametrize("result", [0, -1])
def test_dialog_closure_denies(modules: tuple, result: int) -> None:
    """Rejected and closed dialogs never authorize execution."""
    approval, review, _ = modules
    request = approval.ApprovalRequest(
        approval.ApprovalPayload("execute_python", b"x"), 30
    )
    dialog = review.create_review_dialog(request)
    dialog.finished.connect.call_args.args[0](result)
    assert request.consume() is None
    assert request.state == approval.ApprovalState.DENIED


@pytest.mark.parametrize(
    "code",
    [
        b"a\x00b",
        b"a\rb",
        b"\xff",
        "x\u202ey".encode(),
        "x\u00a0y".encode(),
        "x\u2003y".encode(),
        "x\u3000y".encode(),
        "x\u115fy".encode(),
        "x\u1160y".encode(),
        "x\u3164y".encode(),
        "x\uffa0y".encode(),
        "x\u2028y".encode(),
        "x\u2029y".encode(),
    ],
)
def test_unreviewable_code_is_denied(modules: tuple, code: bytes) -> None:
    """Reject invalid text and characters that could mislead the reviewer."""
    approval, review, _ = modules
    request = approval.ApprovalRequest(
        approval.ApprovalPayload("execute_python", code), 30
    )
    with pytest.raises((ValueError, UnicodeDecodeError)):
        review.create_review_dialog(request)
    assert request.consume() is None
    assert request.state == approval.ApprovalState.DENIED


def test_review_text_limit_counts_utf8_bytes(modules: tuple) -> None:
    """Accept the exact byte limit and reject a larger multibyte payload."""
    _, review, _ = modules
    text = "é" * (review.MAX_REVIEW_BYTES // 2)
    assert review.review_text(text.encode("utf-8")) == text
    with pytest.raises(ValueError, match="size limit"):
        review.review_text((text + "é").encode("utf-8"))


def test_no_gui_cancels_request(modules: tuple) -> None:
    """A missing GUI cannot fall back to implicit approval."""
    approval, review, widgets = modules
    widgets.QApplication.instance.return_value = None
    request = approval.ApprovalRequest(
        approval.ApprovalPayload("execute_python", b"x"), 30
    )
    with pytest.raises(RuntimeError, match="Qt GUI thread"):
        review.create_review_dialog(request)
    assert request.state == approval.ApprovalState.DENIED


def test_destroyed_dialog_cancels_unclaimed_approval(modules: tuple) -> None:
    """Destruction cannot leave an unclaimed authorization alive."""
    approval, review, _ = modules
    request = approval.ApprovalRequest(
        approval.ApprovalPayload("execute_python", b"x"), 30
    )
    dialog = review.create_review_dialog(request)
    dialog.finished.connect.call_args.args[0](1)
    dialog.destroyed.connect.call_args.args[0]()
    assert request.consume() is None


def test_widget_text_mismatch_denies(modules: tuple) -> None:
    """Do not approve if the widget cannot represent the entire input."""
    approval, review, widgets = modules
    editor = widgets.QPlainTextEdit.return_value
    editor.setPlainText.side_effect = None
    editor.toPlainText.return_value = "truncated"
    request = approval.ApprovalRequest(
        approval.ApprovalPayload("execute_python", b"complete"), 30
    )
    with pytest.raises(ValueError, match="exact code"):
        review.create_review_dialog(request)
    assert request.state == approval.ApprovalState.DENIED


def test_controller_serializes_dialogs_and_retains_approval(modules: tuple) -> None:
    """The next review waits until the previous approval is consumed."""
    approval, review, widgets = modules
    coordinator = approval.ReviewCoordinator(2)
    first = coordinator.submit(approval.ApprovalPayload("execute_python", b"one"), 30)
    second = coordinator.submit(approval.ApprovalPayload("execute_python", b"two"), 30)
    controller = review.ReviewDialogController(coordinator)
    controller.poll()
    dialog = widgets.QDialog.return_value
    assert controller._request is first
    dialog.finished.connect.call_args.args[0](1)
    controller.poll()
    assert controller._request is first
    assert coordinator.wait_and_schedule(first)
    assert coordinator.next_execution() == (first.request_id, first.payload)
    controller.poll()
    assert controller._request is second
    controller.close()
    assert second.consume() is None


def test_controller_shutdown_denies_open_review(modules: tuple) -> None:
    """Shutdown closes the dialog and prevents a later affirmative signal."""
    approval, review, widgets = modules
    coordinator = approval.ReviewCoordinator(1)
    request = coordinator.submit(approval.ApprovalPayload("execute_python", b"x"), 30)
    controller = review.ReviewDialogController(coordinator)
    controller.poll()
    dialog = widgets.QDialog.return_value
    finished = dialog.finished.connect.call_args.args[0]
    controller.close()
    finished(1)
    assert request.consume() is None
    assert coordinator.next_execution() is None
    dialog.reject.assert_called_once()
    dialog.deleteLater.assert_called_once()


@pytest.mark.parametrize("result,expected", [(0, False), (1, True)])
def test_timed_bypass_requires_affirmative_decision(
    modules: tuple, result: int, expected: bool
) -> None:
    """Only an accepted dialog can grant the selected time-limited bypass."""
    approval, review, widgets = modules
    policy = MagicMock()
    policy.timed_bypass_enabled.return_value = True
    widgets.QCheckBox.return_value.isChecked.return_value = True
    widgets.QSpinBox.return_value.value.return_value = 15
    request = approval.ApprovalRequest(
        approval.ApprovalPayload("execute_python", b"pass"), 30
    )
    dialog = review.create_review_dialog(request, policy=policy)
    handler = dialog.finished.connect.call_args.args[0]
    handler(result)
    handler(1)
    if expected:
        policy.grant_bypass.assert_called_once_with("execute_python", 900)
        assert request.consume() == request.payload
    else:
        policy.grant_bypass.assert_not_called()
        assert request.consume() is None


def test_controller_applies_local_bypass_deadline(
    modules: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An auto-approved request cannot be claimed after bypass expiry."""
    from types import SimpleNamespace

    approval, review, widgets = modules
    clock = [100.0]
    bypass_clock = [100.0]
    monkeypatch.setattr(approval, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    coordinator = approval.ReviewCoordinator(1)
    request = coordinator.submit(
        approval.ApprovalPayload("execute_python", b"pass"), 30
    )
    policy = MagicMock()
    policy.now.side_effect = lambda: bypass_clock[0]
    policy.decision.return_value = (False, 101.0)
    controller = review.ReviewDialogController(coordinator, policy=policy)
    controller.poll()
    widgets.QDialog.assert_not_called()
    assert coordinator.wait_and_schedule(request)
    # Simulate sleep: elapsed time advances while the request clock pauses.
    bypass_clock[0] = 101.0
    assert coordinator.next_execution() is None
    controller.close()
    policy.clear_session.assert_called_once()
