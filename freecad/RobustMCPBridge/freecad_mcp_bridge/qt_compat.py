"""Resolve the PySide binding that matches FreeCAD's loaded Qt runtime.

Qt 5 and Qt 6 cannot safely coexist in one process. FreeCAD exposes a
version-neutral ``PySide`` module for its active Qt runtime. Prefer its modules
after validating the host Qt version, falling back only to the matching binding.
If the host signal is unavailable, prefer PySide6 and then PySide2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType


def get_host_qt_binding() -> str | None:
    """Return the PySide binding matching FreeCAD's active Qt major version.

    Returns:
        ``"PySide6"`` for a Qt 6 host, ``"PySide2"`` for a Qt 5 host, or
        ``None`` when FreeCAD's version-neutral PySide module is unavailable.

    Raises:
        RuntimeError: If FreeCAD reports an unsupported Qt major version.
    """
    try:
        host_pyside = __import__("PySide", fromlist=["QtCore"])
        host_qt_core = host_pyside.QtCore
        qt_major = int(str(host_qt_core.qVersion()).split(".", 1)[0])
    except (AttributeError, ImportError, NameError, TypeError, ValueError):
        return None

    if qt_major == 6:
        return "PySide6"
    if qt_major == 5:
        return "PySide2"
    raise RuntimeError(f"Unsupported FreeCAD Qt major version: {qt_major}")


def load_qt_modules(*module_names: str) -> tuple[ModuleType, ...]:
    """Load Qt modules without mixing Qt major versions in one process.

    Args:
        *module_names: Module attributes to load, such as ``QtCore`` and
            ``QtWidgets``.

    Returns:
        Requested module objects in the same order as ``module_names``.

    Raises:
        ValueError: If no module names are supplied.
        RuntimeError: If the host-matching binding, or both fallback bindings,
            cannot be loaded.
    """
    if not module_names:
        raise ValueError("At least one Qt module name is required")

    host_binding = get_host_qt_binding()
    if host_binding:
        try:
            host_pyside = __import__("PySide", fromlist=list(module_names))
            return tuple(getattr(host_pyside, name) for name in module_names)
        except (AttributeError, ImportError, NameError):
            pass
    candidates = (host_binding,) if host_binding else ("PySide6", "PySide2")
    last_error: BaseException | None = None

    for binding in candidates:
        try:
            pyside = __import__(binding, fromlist=list(module_names))
            return tuple(getattr(pyside, name) for name in module_names)
        except (AttributeError, ImportError, NameError) as error:
            last_error = error

    requested = ", ".join(module_names)
    if host_binding:
        other_binding = "PySide2" if host_binding == "PySide6" else "PySide6"
        message = (
            f"FreeCAD uses {host_binding}, but its {requested} modules could not "
            f"be loaded. Refusing to load {other_binding} into the same process."
        )
    else:
        message = (
            f"Neither PySide6 nor PySide2 could provide the requested Qt modules: "
            f"{requested}."
        )
    raise RuntimeError(message) from last_error


def load_qt_core() -> Any:
    """Load and return the host-compatible QtCore module."""
    return load_qt_modules("QtCore")[0]


def load_qt_core_widgets() -> tuple[Any, Any]:
    """Load and return host-compatible QtCore and QtWidgets modules."""
    qt_core, qt_widgets = load_qt_modules("QtCore", "QtWidgets")
    return qt_core, qt_widgets
