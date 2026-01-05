"""Pytest configuration for integration tests.

This module handles connection checking and provides consolidated skip behavior
when the FreeCAD MCP bridge is not available.

Instance ID Verification:
    The FreeCAD MCP bridge generates a unique instance ID at startup which is
    printed to stdout. Tests can capture this ID and verify they're connected
    to the expected instance using the `bridge_instance_id` fixture or by
    calling proxy.get_instance_id().
"""

from __future__ import annotations

import os
import warnings
import xmlrpc.client
from typing import Any

import pytest

# Global flag to track bridge availability (checked once per session)
_bridge_available: bool | None = None
_bridge_error: str | None = None
_bridge_instance_id: str | None = None
_gui_available: bool | None = None
_warning_emitted: bool = False


def _check_bridge_connection() -> tuple[bool, str | None, str | None]:
    """Check if the FreeCAD MCP bridge is available and get its instance ID.

    Returns:
        Tuple of (is_available, error_message, instance_id)
    """
    global _bridge_available, _bridge_error, _bridge_instance_id, _gui_available

    if _bridge_available is not None:
        return _bridge_available, _bridge_error, _bridge_instance_id

    try:
        proxy = xmlrpc.client.ServerProxy("http://localhost:9875", allow_none=True)
        result: dict[str, Any] = proxy.ping()  # type: ignore[assignment]
        if result.get("pong"):
            _bridge_available = True
            _bridge_error = None
            # The ping response includes instance_id
            _bridge_instance_id = result.get("instance_id")

            # Check if GUI is available via get_status
            try:
                status: dict[str, Any] = proxy.get_status()  # type: ignore[assignment]
                _gui_available = status.get("gui_available", False)
            except Exception:
                # If get_status fails, assume headless
                _gui_available = False
        else:
            _bridge_available = False
            _bridge_error = "FreeCAD MCP bridge not responding to ping"
            _bridge_instance_id = None
            _gui_available = None
    except ConnectionRefusedError:
        _bridge_available = False
        _bridge_error = "Connection refused - FreeCAD MCP bridge not running"
        _bridge_instance_id = None
        _gui_available = None
    except Exception as e:
        _bridge_available = False
        _bridge_error = f"Cannot connect to FreeCAD MCP bridge: {e}"
        _bridge_instance_id = None
        _gui_available = None

    return _bridge_available, _bridge_error, _bridge_instance_id


def is_gui_available() -> bool:
    """Check if FreeCAD GUI is available.

    Returns:
        True if running in GUI mode, False if headless.
    """
    # Ensure bridge check has been performed
    _check_bridge_connection()
    return _gui_available is True


def is_headless_mode() -> bool:
    """Check if FreeCAD is running in headless mode.

    Returns:
        True if running in headless mode, False if GUI is available.
    """
    return not is_gui_available()


# Skip marker for GUI-only tests
requires_gui = pytest.mark.skipif(
    is_headless_mode(),
    reason="Test requires FreeCAD GUI mode (running in headless mode)",
)


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Skip all integration tests if the bridge is not available.

    This runs once during test collection and emits a single warning instead of
    per-test skip messages.
    """
    global _warning_emitted

    # Filter to only integration tests in this directory
    integration_tests = [
        item for item in items if "tests/integration" in str(item.fspath)
    ]

    if not integration_tests:
        return

    # Check bridge connection once
    is_available, error, instance_id = _check_bridge_connection()

    if not is_available:
        # Apply skip marker to all integration tests
        skip_marker = pytest.mark.skip(reason="FreeCAD MCP bridge unavailable")
        for item in integration_tests:
            item.add_marker(skip_marker)

        # Emit a single warning (only once)
        if not _warning_emitted:
            _warning_emitted = True
            warnings.warn(
                f"Skipping {len(integration_tests)} integration tests: {error}. "
                f"Start the bridge with 'just run-gui' or 'just run-headless'.",
                pytest.PytestWarning,
                stacklevel=1,
            )


@pytest.fixture(scope="module")
def xmlrpc_proxy() -> xmlrpc.client.ServerProxy:
    """Create XML-RPC proxy to FreeCAD MCP bridge.

    This fixture is shared across all integration test modules.
    The connection check has already been performed during collection.
    """
    is_available, error, _ = _check_bridge_connection()
    if not is_available:
        pytest.skip(error or "FreeCAD MCP bridge not available")

    return xmlrpc.client.ServerProxy("http://localhost:9875", allow_none=True)


@pytest.fixture(scope="module")
def bridge_instance_id() -> str | None:
    """Get the instance ID of the connected FreeCAD MCP bridge.

    This fixture returns the unique instance ID that was generated when
    the bridge started. Use this to verify you're connected to the expected
    bridge instance.

    Returns:
        The instance ID string, or None if not available.
    """
    is_available, _, instance_id = _check_bridge_connection()
    if not is_available:
        return None
    return instance_id


@pytest.fixture(scope="module")
def expected_bridge_instance_id() -> str | None:
    """Get the expected bridge instance ID from environment variable.

    When running tests that start the bridge themselves (e.g., in CI),
    the startup script can capture the instance ID from the bridge's
    stdout and set it as EXPECTED_BRIDGE_INSTANCE_ID environment variable.

    Returns:
        The expected instance ID from env, or None if not set.
    """
    return os.environ.get("EXPECTED_BRIDGE_INSTANCE_ID")


@pytest.fixture(scope="module")
def freecad_gui_available() -> bool:
    """Check if FreeCAD GUI is available.

    This fixture returns True if FreeCAD is running in GUI mode,
    False if running in headless mode. Use this to conditionally
    skip tests that require GUI features.

    Returns:
        True if GUI is available, False if headless.

    Example:
        def test_screenshot(freecad_gui_available):
            if not freecad_gui_available:
                pytest.skip("Test requires GUI mode")
            # ... test that needs GUI
    """
    return is_gui_available()


@pytest.fixture(scope="module")
def freecad_is_headless() -> bool:
    """Check if FreeCAD is running in headless mode.

    This fixture returns True if FreeCAD is running in headless mode
    (no GUI), False if GUI is available.

    Returns:
        True if headless, False if GUI is available.

    Example:
        def test_some_feature(freecad_is_headless):
            if freecad_is_headless:
                pytest.skip("Test requires GUI mode")
            # ... test that needs GUI
    """
    return is_headless_mode()


def verify_bridge_instance(
    proxy: xmlrpc.client.ServerProxy,
    expected_id: str | None,
) -> bool:
    """Verify we're connected to the expected bridge instance.

    Args:
        proxy: XML-RPC proxy to the bridge.
        expected_id: Expected instance ID, or None to skip verification.

    Returns:
        True if verification passed or was skipped (no expected_id).

    Raises:
        AssertionError: If instance ID doesn't match expected.
    """
    if expected_id is None:
        return True

    result: dict[str, Any] = proxy.get_instance_id()  # type: ignore[assignment]
    actual_id = result.get("instance_id")

    if actual_id != expected_id:
        msg = (
            f"Bridge instance ID mismatch!\n"
            f"  Expected: {expected_id}\n"
            f"  Actual:   {actual_id}\n"
            f"This may indicate you're connected to a different bridge instance."
        )
        raise AssertionError(msg)

    return True
