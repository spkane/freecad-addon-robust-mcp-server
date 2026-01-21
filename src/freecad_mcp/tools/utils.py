"""Utility functions for FreeCAD MCP tools.

This module provides shared utilities for tool implementations,
including transaction wrapping for undo support.
"""

import textwrap


def wrap_with_transaction(
    code: str,
    transaction_name: str,
    doc_expr: str = "FreeCAD.ActiveDocument",
) -> str:
    """Wrap Python code with FreeCAD transaction for undo support.

    FreeCAD transactions enable undo/redo functionality. All modifying
    operations should be wrapped in transactions so users can easily
    undo changes if something goes wrong.

    Args:
        code: The Python code to wrap. Should set `_result_` for return value.
        transaction_name: Human-readable name for the transaction (shown in undo menu).
        doc_expr: Expression to get the document. Defaults to "FreeCAD.ActiveDocument".

    Returns:
        Code string wrapped with transaction open/commit/abort handling.

    Example:
        >>> code = '''
        ... box = doc.addObject("Part::Box", "MyBox")
        ... box.Length = 10
        ... _result_ = {"name": box.Name}
        ... '''
        >>> wrapped = wrap_with_transaction(code, "Create Box")
    """
    # Indent the original code for the try block
    indented_code = textwrap.indent(code.strip(), "    ")

    return f"""_txn_doc = {doc_expr}
if _txn_doc is not None:
    _txn_doc.openTransaction({transaction_name!r})
try:
{indented_code}
    if _txn_doc is not None:
        _txn_doc.commitTransaction()
except Exception as _txn_error:
    if _txn_doc is not None:
        _txn_doc.abortTransaction()
    raise _txn_error
"""
