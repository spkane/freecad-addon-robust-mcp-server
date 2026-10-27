"""Check that the authenticated FreeCAD bridge reports an active GUI."""

from tests.integration.auth_support import integration_proxy


def gui_is_ready() -> bool:
    """Return true only for a successful execution reporting an active GUI."""
    result = integration_proxy().execute("_result_ = bool(FreeCAD.GuiUp)")
    return (
        isinstance(result, dict)
        and result.get("success") is True
        and result.get("result") is True
    )


if __name__ == "__main__":
    raise SystemExit(0 if gui_is_ready() else 1)
