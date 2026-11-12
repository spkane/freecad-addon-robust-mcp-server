"""Exercise the prototype review dialog using a real offscreen PySide6 GUI.

Run in a disposable process with ``QT_QPA_PLATFORM=offscreen uv run python
 tests/research/approval_qt_probe.py``. This tests the Python environment's Qt,
not the Qt bundled with an actual FreeCAD host.
"""

import sys
import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication, QCheckBox, QPlainTextEdit, QSpinBox

ADDON = Path(__file__).resolve().parents[2] / "freecad" / "RobustMCPBridge"
sys.path.insert(0, str(ADDON))

from freecad_mcp_bridge.approval import (  # noqa: E402
    ApprovalPayload,
    ApprovalRequest,
    ReviewCoordinator,
)
from freecad_mcp_bridge.review_dialog import (  # noqa: E402
    ReviewDialogController,
    create_close_relay,
    create_review_dialog,
)
from freecad_mcp_bridge.review_policy import ReviewPolicy  # noqa: E402


def main() -> None:
    """Check that accepting approves and closing denies using real Qt signals."""
    app = QApplication([])
    request = ApprovalRequest(ApprovalPayload("execute_python", b"print(1)\n"), 30)
    dialog = create_review_dialog(request)
    dialog.open()
    app.processEvents()
    dialog.accept()
    app.processEvents()
    assert request.consume() == request.payload
    denied = ApprovalRequest(ApprovalPayload("execute_python", b"print(2)"), 30)
    closed = create_review_dialog(denied)
    closed.open()
    app.processEvents()
    closed.close()
    app.processEvents()
    assert denied.consume() is None
    long_code = "# review line\n" * 3000 + "_result_ = 7\n"
    long_request = ApprovalRequest(
        ApprovalPayload("execute_python", long_code.encode("utf-8")), 30
    )
    long_dialog = create_review_dialog(long_request)
    long_dialog.open()
    app.processEvents()
    editor = long_dialog.findChild(QPlainTextEdit)
    assert editor is not None and editor.toPlainText() == long_code
    scroll = editor.verticalScrollBar()
    assert scroll.maximum() > 0
    scroll.setValue(scroll.maximum())
    assert scroll.value() == scroll.maximum()
    long_dialog.accept()
    app.processEvents()
    assert long_request.consume() == long_request.payload
    policy = ReviewPolicy()
    policy.set_timed_bypass_enabled(True)
    timed = ApprovalRequest(ApprovalPayload("execute_python", b"pass"), 30)
    timed_dialog = create_review_dialog(timed, policy=policy)
    timed_dialog.open()
    app.processEvents()
    checkbox = timed_dialog.findChild(QCheckBox)
    duration = timed_dialog.findChild(QSpinBox)
    assert checkbox is not None and duration is not None
    checkbox.setChecked(True)
    duration.setValue(1)
    timed_dialog.accept()
    app.processEvents()
    assert timed.consume() == timed.payload
    assert not policy.requires_review("execute_python")
    policy.clear_session()
    assert policy.requires_review("execute_python")
    coordinator = ReviewCoordinator(1)
    pending = coordinator.submit(ApprovalPayload("execute_python", b"print(3)"), 30)
    controller = ReviewDialogController(coordinator)
    controller.poll()
    app.processEvents()
    assert controller._dialog is not None
    controller._dialog.accept()
    app.processEvents()
    assert coordinator.wait_and_schedule(pending)
    assert coordinator.next_execution() == (pending.request_id, pending.payload)
    controller.poll()
    controller.close()
    app.processEvents()
    worker_coordinator = ReviewCoordinator(1)
    pending_worker = worker_coordinator.submit(
        ApprovalPayload("execute_python", b"print(4)"), 30
    )
    worker_controller = ReviewDialogController(worker_coordinator)
    worker_controller.poll()
    app.processEvents()
    assert worker_controller._dialog is not None
    relay = create_close_relay(worker_controller)

    def request_shutdown() -> None:
        worker_coordinator.close()
        relay.requested.emit()

    worker = threading.Thread(target=request_shutdown)
    worker.start()
    worker.join(2)
    assert not worker.is_alive()
    for _ in range(10):
        app.processEvents()
        if worker_controller._closed:
            break
    assert worker_controller._closed
    assert pending_worker.consume() is None
    print("Qt6 offscreen accept and close passed")


if __name__ == "__main__":
    main()
