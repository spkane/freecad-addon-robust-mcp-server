"""Build a local, default-deny review dialog for bridge approval requests.

Dialog creation and signal handling must take place on FreeCAD's Qt main
thread. The caller owns the returned dialog until it finishes and must cancel
pending requests on shutdown.
"""

from __future__ import annotations

import hashlib
import unicodedata
from typing import TYPE_CHECKING, Any

if __package__:
    from .approval import ApprovalState
    from .qt_compat import load_qt_core_widgets
else:
    from approval import ApprovalState  # type: ignore[import-not-found,no-redef]
    from qt_compat import load_qt_core_widgets  # type: ignore[import-not-found,no-redef]

if TYPE_CHECKING:
    from .approval import ApprovalRequest

MAX_REVIEW_BYTES = 64 * 1024
_INVISIBLE_LETTERS = frozenset("\u115f\u1160\u3164\uffa0")


def review_text(content: bytes, *, allow_crlf: bool = False) -> str:
    """Decode bounded code without invisible control or bidirectional characters.

    The returned string is shown as plain text, without rewriting the bytes
    retained by the request. Tabs and line feeds are permitted. Refuse bytes
    that cannot be faithfully displayed instead of silently replacing them.

    Raises:
        ValueError: If content exceeds the limit or contains unsafe characters.
        UnicodeDecodeError: If the bytes are not valid UTF-8.
    """
    if len(content) > MAX_REVIEW_BYTES:
        raise ValueError("Code exceeds the review size limit")
    text = content.decode("utf-8", errors="strict")
    if allow_crlf:
        text = text.replace("\r\n", "\n")
    if any(
        (
            unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
            or (unicodedata.category(character) == "Zs" and character != " ")
            or character in _INVISIBLE_LETTERS
        )
        and character not in "\n\t"
        for character in text
    ):
        raise ValueError("Code contains unsupported control or whitespace characters")
    return text


def create_review_dialog(  # noqa: PLR0912
    request: ApprovalRequest,
    parent: Any = None,
    policy: Any = None,
    approval_store: Any = None,
) -> Any:
    """Create a nonblocking default-deny dialog for an exact pending request.

    Returns the dialog for the caller to retain and open on the Qt main thread.
    Closing, rejecting, errors, and late decisions cannot approve the request.
    This function never executes the reviewed content.

    Raises:
        RuntimeError: If a GUI application or its main thread is unavailable.
        ValueError: If the action or displayed content cannot be reviewed safely.
    """
    try:
        action = request.payload.action
        code = review_text(request.payload.content, allow_crlf=action == "run_macro")
        if action not in {"execute_python", "run_macro"}:
            raise ValueError("Unsupported action for code review")
        macro_approval = None
        if action == "run_macro":
            payload = request.payload
            if (
                payload.macro_path is None
                or payload.macro_sha256 is None
                or payload.macro_args_json is None
                or hashlib.sha256(payload.content).hexdigest() != payload.macro_sha256
            ):
                raise ValueError("Invalid macro review payload")
            if __package__:
                from .macro_approvals import MacroApproval
            else:
                from macro_approvals import MacroApproval  # type: ignore[import-not-found,no-redef]
            macro_approval = MacroApproval(payload.macro_path, payload.macro_sha256)
            review_text(payload.macro_path.encode("utf-8"))
            review_text(payload.macro_args_json.encode("utf-8"))
        qtcore, qtwidgets = load_qt_core_widgets()
        app = qtwidgets.QApplication.instance()
        if app is None or qtcore.QThread.currentThread() != app.thread():
            raise RuntimeError("Approval dialog requires the Qt GUI thread")
        dialog = qtwidgets.QDialog(parent)
        dialog.setWindowTitle(
            "Review macro execution"
            if action == "run_macro"
            else "Review Python execution"
        )
        dialog.resize(800, 600)
        layout = qtwidgets.QVBoxLayout(dialog)
        warning = qtwidgets.QLabel(
            "An authorized client requests Python execution with your FreeCAD "
            "user permissions, including access to files and the network. "
            "Review all code before allowing this request. The request expires "
            "after about five minutes or sooner if the client disconnects."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        if macro_approval is not None:
            details = qtwidgets.QPlainTextEdit(dialog)
            details.setReadOnly(True)
            details_text = (
                f"Macro path: {payload.macro_path}\nSHA-256: {payload.macro_sha256}\n"
                f"Arguments: {payload.macro_args_json}"
            )
            if b"\r\n" in payload.content:
                details_text += "\nCRLF line endings are displayed and executed as LF."
            details.setPlainText(details_text)
            if details.toPlainText() != details_text:
                raise ValueError(
                    "The review widget could not display the macro details"
                )
            details.setMaximumHeight(140)
            layout.addWidget(details)
        editor = qtwidgets.QPlainTextEdit(dialog)
        editor.setReadOnly(True)
        editor.setPlainText(code)
        if editor.toPlainText() != code:
            raise ValueError("The review widget could not display the exact code")
        layout.addWidget(editor)
        remember_check = None
        if macro_approval is not None and approval_store is not None:
            remember_check = qtwidgets.QCheckBox(
                "Always allow this exact macro version"
            )
            remember_check.setToolTip(
                "Future requests for this path and checksum can run without review. "
                "Arguments and imported files may still change."
            )
            layout.addWidget(remember_check)
            remember_warning = qtwidgets.QLabel(
                "Saved approval applies to this file path and its exact contents. "
                "Arguments, imported files, and other dependencies may change."
            )
            remember_warning.setWordWrap(True)
            layout.addWidget(remember_warning)
        bypass_check = None
        bypass_minutes = None
        if policy is not None and policy.timed_bypass_enabled():
            bypass_check = qtwidgets.QCheckBox(
                "Also bypass local macro review for a limited time"
                if action == "run_macro"
                else "Also bypass local Python review for a limited time"
            )
            bypass_minutes = qtwidgets.QSpinBox()
            bypass_minutes.setRange(1, 480)
            bypass_minutes.setValue(15)
            bypass_minutes.setSuffix(" minutes")
            layout.addWidget(bypass_check)
            layout.addWidget(bypass_minutes)
            bypass_warning = qtwidgets.QLabel(
                "While bypassed, authorized clients can run "
                + ("macros" if action == "run_macro" else "Python")
                + " without this review, including access to files and the network."
            )
            bypass_warning.setWordWrap(True)
            layout.addWidget(bypass_warning)
        buttons = qtwidgets.QDialogButtonBox(dialog)
        deny = buttons.addButton("Deny", qtwidgets.QDialogButtonBox.RejectRole)
        allow = buttons.addButton("Allow once", qtwidgets.QDialogButtonBox.AcceptRole)
        deny.setDefault(True)
        deny.setAutoDefault(True)
        allow.setAutoDefault(False)
        if bypass_check is not None and bypass_minutes is not None:
            bypass_minutes.setEnabled(False)
            bypass_check.toggled.connect(bypass_minutes.setEnabled)
            bypass_check.toggled.connect(
                lambda checked: allow.setText(
                    "Allow and bypass" if checked else "Allow once"
                )
            )
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        def finished(result: int) -> None:
            accepted = result == qtwidgets.QDialog.Accepted
            decided = request.decide(approved=accepted)
            if (
                accepted
                and decided
                and remember_check is not None
                and remember_check.isChecked()
            ):
                try:
                    approval_store.add(macro_approval)
                except Exception:
                    request.cancel()
                    qtwidgets.QMessageBox.warning(
                        dialog,
                        "Macro approval",
                        "Could not save the approval; the request was denied.",
                    )
                    return
            if (
                accepted
                and decided
                and bypass_check is not None
                and bypass_check.isChecked()
                and bypass_minutes is not None
            ):
                policy.grant_bypass(request.payload.action, bypass_minutes.value() * 60)

        dialog.finished.connect(finished)
        dialog.destroyed.connect(lambda *_args: request.cancel())
        return dialog
    except Exception:
        request.cancel()
        raise


class ReviewDialogController:
    """Show at most one local review at a time from a Qt main-thread timer.

    The controller retains each dialog until its request is consumed or denied,
    preventing garbage collection from revoking an approved but unclaimed
    request. It does not start a timer or connect itself to a bridge listener.
    """

    def __init__(
        self,
        coordinator: Any,
        parent: Any = None,
        policy: Any = None,
        approval_store: Any = None,
    ) -> None:
        """Initialize the controller for an existing review coordinator."""
        self._coordinator = coordinator
        self._parent = parent
        self._policy = policy
        self._approval_store = approval_store
        self._request: ApprovalRequest | None = None
        self._dialog: Any = None
        self._closed = False

    def poll(self) -> None:  # noqa: PLR0912
        """Process one review request; call only on the Qt main thread."""
        if self._closed:
            return
        if self._request is not None:
            if self._request.state in (ApprovalState.PENDING, ApprovalState.APPROVED):
                return
            self._dispose_dialog()
        request = self._coordinator.next_review()
        if request is None:
            return
        try:
            if self._policy is not None:
                required, deadline = self._policy.decision(request.payload.action)
                if not required:
                    if deadline is None:
                        request.decide(approved=True)
                    elif not request.approve_until(deadline, self._policy.now):
                        self._coordinator.cancel(request)
                    return
            if (
                request.payload.action == "run_macro"
                and self._approval_store is not None
            ):
                if __package__:
                    from .macro_approvals import MacroApproval
                else:
                    from macro_approvals import MacroApproval  # type: ignore[import-not-found,no-redef]
                payload = request.payload
                entry = MacroApproval(payload.macro_path, payload.macro_sha256)
                if self._approval_store.contains(entry):
                    if not request.approve_if_still_valid(
                        lambda: self._approval_store.contains(entry)
                    ):
                        self._coordinator.cancel(request)
                    return
            dialog = create_review_dialog(
                request, self._parent, self._policy, self._approval_store
            )
            self._request = request
            self._dialog = dialog
            dialog.open()
        except Exception:
            self._coordinator.cancel(request)
            self._dispose_dialog()

    def _dispose_dialog(self) -> None:
        dialog, self._dialog = self._dialog, None
        self._request = None
        if dialog is not None:
            dialog.reject()
            dialog.deleteLater()

    def close(self) -> None:
        """Cancel pending reviews and close the active dialog on the Qt thread."""
        if self._closed:
            return
        self._closed = True
        if self._policy is not None:
            self._policy.clear_session()
        self._coordinator.close()
        self._dispose_dialog()


def create_close_relay(controller: ReviewDialogController) -> Any:
    """Create a GUI-thread QObject that can close the controller from a worker.

    The caller must create and retain this relay on the Qt GUI thread. Emitting
    ``requested`` from a worker queues dialog disposal onto that thread. The
    coordinator must be closed synchronously before the signal is emitted.
    """
    qtcore, qtwidgets = load_qt_core_widgets()
    app = qtwidgets.QApplication.instance()
    if app is None or qtcore.QThread.currentThread() != app.thread():
        raise RuntimeError("Review close relay requires the Qt GUI thread")

    class CloseRelay(qtcore.QObject):  # type: ignore[name-defined]
        requested = qtcore.Signal()

        def __init__(self) -> None:
            super().__init__()
            self.requested.connect(self.close_review, qtcore.Qt.QueuedConnection)

        @qtcore.Slot()
        def close_review(self) -> None:
            controller.close()

    return CloseRelay()
