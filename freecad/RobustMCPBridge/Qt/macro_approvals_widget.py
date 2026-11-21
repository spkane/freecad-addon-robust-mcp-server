"""Manage locally saved exact-version macro approvals in FreeCAD preferences."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..freecad_mcp_bridge.macro_approvals import freecad_approval_store
from ..freecad_mcp_bridge.qt_compat import load_qt_core_widgets, load_qt_modules

if TYPE_CHECKING:
    from PySide6 import QtCore, QtWidgets
else:
    QtCore, QtWidgets = load_qt_core_widgets()


class MacroApprovalsWidget(QtWidgets.QWidget):
    """Display and revoke locally approved macro paths and checksums."""

    def __init__(self, parent: Any = None, store: Any = None) -> None:
        """Create a scrollable table backed by local FreeCAD preferences."""
        super().__init__(parent)
        self._store = store if store is not None else freecad_approval_store()
        self._entries: tuple[Any, ...] = ()
        layout = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(
            "Saved approvals apply to the exact file path and SHA-256 shown. "
            "Arguments and imported files are not covered. Removing an approval "
            "takes effect immediately."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QtWidgets.QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Macro path", "SHA-256"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setMinimumHeight(130)
        layout.addWidget(self.table)
        self.error = QtWidgets.QLabel("")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        actions = QtWidgets.QHBoxLayout()
        self.open_button = QtWidgets.QPushButton("Open enclosing folder")
        self.remove_button = QtWidgets.QPushButton("Remove approval")
        self.clear_button = QtWidgets.QPushButton("Remove all approvals")
        self.open_button.clicked.connect(self.open_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_all)
        actions.addWidget(self.open_button)
        actions.addWidget(self.remove_button)
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        """Reload the saved list; invalid storage never grants approval."""
        self.table.setRowCount(0)
        self._entries = ()
        try:
            self._entries = self._store.entries()
            self.error.setText("")
            self.table.setRowCount(len(self._entries))
            for row, entry in enumerate(self._entries):
                path_item = QtWidgets.QTableWidgetItem(entry.path)
                path_item.setToolTip(entry.path)
                self.table.setItem(row, 0, path_item)
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(entry.sha256))
        except (ValueError, OSError, TypeError):
            self.error.setText(
                "Saved macro approvals could not be read. No saved approval will "
                "be used; remove all approvals to reset the list."
            )

    def _selected(self) -> Any:
        row = self.table.currentRow()
        return self._entries[row] if 0 <= row < len(self._entries) else None

    def open_folder(self) -> None:
        """Open the selected macro's containing directory in the system browser."""
        entry = self._selected()
        if entry is None:
            return
        qtgui = load_qt_modules("QtGui")[0]
        url = QtCore.QUrl.fromLocalFile(str(Path(entry.path).parent))
        if not qtgui.QDesktopServices.openUrl(url):
            QtWidgets.QMessageBox.warning(
                self, "Macro approvals", "Could not open the folder."
            )

    def remove_selected(self) -> None:
        """Immediately remove the selected path and checksum pair."""
        entry = self._selected()
        if entry is None:
            return
        try:
            self._store.remove(entry)
        except (ValueError, OSError, TypeError):
            QtWidgets.QMessageBox.warning(
                self, "Macro approvals", "Could not remove the approval."
            )
        self.refresh()

    def clear_all(self) -> None:
        """Confirm before immediately removing every locally saved approval."""
        answer = QtWidgets.QMessageBox.question(
            self,
            "Remove all approvals",
            "Remove all saved macro approvals? Future requests require review "
            "unless a timed macro-review bypass is active.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            self._store.clear()
        except (ValueError, OSError, TypeError):
            QtWidgets.QMessageBox.warning(
                self, "Macro approvals", "Could not remove approvals."
            )
        self.refresh()
