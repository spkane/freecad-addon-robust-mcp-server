"""Exercise the approval table with real Qt in an isolated offscreen process.

Run with ``QT_QPA_PLATFORM=offscreen``. This does not substitute for testing
the preferences page in FreeCAD's own Qt runtime.
"""

import importlib
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

from PySide6.QtWidgets import QApplication, QMessageBox

ADDON = Path(__file__).resolve().parents[2] / "freecad" / "RobustMCPBridge"


def package(name: str, path: Path) -> None:
    """Install an isolated package namespace without starting the workbench."""
    module = ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


def main() -> None:
    """Check scrolling, exact-entry removal, and the local folder action."""
    package("macro_probe", ADDON)
    package("macro_probe.Qt", ADDON / "Qt")
    package("macro_probe.freecad_mcp_bridge", ADDON / "freecad_mcp_bridge")
    approvals = importlib.import_module(
        "macro_probe.freecad_mcp_bridge.macro_approvals"
    )
    widget_module = importlib.import_module("macro_probe.Qt.macro_approvals_widget")
    approval = importlib.import_module("macro_probe.freecad_mcp_bridge.approval")
    review = importlib.import_module("macro_probe.freecad_mcp_bridge.review_dialog")
    app = QApplication([])
    storage = [""]
    store = approvals.MacroApprovalStore(
        lambda: storage[0], lambda v: storage.__setitem__(0, v)
    )
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        items = [
            approvals.MacroApproval(str(root / f"macro-{i}.FCMacro"), f"{i:064x}")
            for i in range(40)
        ]
        for item in items:
            store.add(item)
        widget = widget_module.MacroApprovalsWidget(store=store)
        widget.resize(700, 250)
        widget.show()
        app.processEvents()
        assert widget.table.rowCount() == 40
        assert widget.table.verticalScrollBar().maximum() > 0
        selected_row = next(
            row
            for row in range(widget.table.rowCount())
            if widget.table.item(row, 0).text() == items[2].path
            and widget.table.item(row, 1).text() == items[2].sha256
        )
        widget.table.selectRow(selected_row)
        opened: list[str] = []

        def open_url(url: object) -> bool:
            opened.append(url.toLocalFile())  # type: ignore[attr-defined]
            return True

        widget_module.load_qt_modules = lambda *_names: (  # type: ignore[attr-defined]
            SimpleNamespace(QDesktopServices=SimpleNamespace(openUrl=open_url)),
        )
        widget.open_folder()
        assert opened == [str(root)]
        coordinator = approval.ReviewCoordinator(2)
        controller = review.ReviewDialogController(coordinator, approval_store=store)
        pending = coordinator.submit(
            approval.ApprovalPayload(
                "run_macro", b"", items[2].path, items[2].sha256, "{}"
            ),
            30,
        )
        controller.poll()
        assert coordinator.wait_and_schedule(pending)
        widget.remove_selected()
        assert coordinator.next_execution() is None
        assert widget.table.rowCount() == 39 and not store.contains(items[2])
        assert store.contains(items[1])
        pending = coordinator.submit(
            approval.ApprovalPayload(
                "run_macro", b"", items[1].path, items[1].sha256, "{}"
            ),
            30,
        )
        controller.poll()
        assert coordinator.wait_and_schedule(pending)
        QMessageBox.question = lambda *_args: QMessageBox.Yes
        widget.clear_all()
        assert coordinator.next_execution() is None
        assert widget.table.rowCount() == 0 and store.entries() == ()
        controller.close()
        widget.close()
    print("Real Qt macro approval table passed")


if __name__ == "__main__":
    main()
