"""Build FreeCAD-side code for reading available console diagnostics."""

from freecad_mcp.bridge.base import ExecutionResult


def validate_console_lines(lines: int) -> None:
    """Reject invalid limits consistently across connection modes."""
    if isinstance(lines, bool) or not isinstance(lines, int) or not 1 <= lines <= 1000:
        raise ValueError("lines must be an integer between 1 and 1000")


def console_output_from_result(result: ExecutionResult) -> list[str]:
    """Extract captured lines while preserving transport failures."""
    if result.success and isinstance(result.result, list):
        return result.result
    message = (
        result.error_traceback or result.stderr or "FreeCAD console capture failed"
    )
    if result.error_type in {"TimeoutError", "RequestNotSentError"}:
        raise TimeoutError(message)
    if result.error_type == "ConnectionError":
        raise ConnectionError(message)
    raise RuntimeError(message)


def build_console_output_code(lines: int) -> str:
    """Build a bounded console query with an explicit unavailable result.

    Args:
        lines: Maximum number of lines to retrieve, from 1 to 1000.

    Returns:
        Python code to execute on FreeCAD's owning thread.

    Raises:
        ValueError: If the line count is outside the supported range.
    """
    validate_console_lines(lines)
    return f"""
output = None
if getattr(FreeCAD, "GuiUp", False):
    import FreeCADGui
    try:
        from PySide import QtWidgets
        text_edit = QtWidgets.QTextEdit
    except (ImportError, AttributeError):
        try:
            from PySide import QtGui
            text_edit = QtGui.QTextEdit
        except (ImportError, AttributeError):
            text_edit = None
    main_window = FreeCADGui.getMainWindow()
    widget = (main_window.findChild(text_edit, "Report view")
              if main_window and text_edit is not None else None)
    if widget is not None:
        output = widget.toPlainText()
if output is None and hasattr(FreeCAD.Console, "GetLog"):
    output = FreeCAD.Console.GetLog()
if output is None:
    raise RuntimeError("FreeCAD console history is unavailable in this session")
_result_ = output.splitlines()[-{lines}:]
"""
