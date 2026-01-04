"""Pytest configuration for integration tests.

This module handles connection checking and provides consolidated skip behavior
when the FreeCAD MCP bridge is not available.
"""

from __future__ import annotations

import warnings
import xmlrpc.client
from typing import Any

import pytest

# Global flag to track bridge availability (checked once per session)
_bridge_available: bool | None = None
_bridge_error: str | None = None
_warning_emitted: bool = False


def _check_bridge_connection() -> tuple[bool, str | None]:
    """Check if the FreeCAD MCP bridge is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    global _bridge_available, _bridge_error

    if _bridge_available is not None:
        return _bridge_available, _bridge_error

    try:
        proxy = xmlrpc.client.ServerProxy("http://localhost:9875", allow_none=True)
        result: dict[str, Any] = proxy.ping()  # type: ignore[assignment]
        if result.get("pong"):
            _bridge_available = True
            _bridge_error = None
        else:
            _bridge_available = False
            _bridge_error = "FreeCAD MCP bridge not responding to ping"
    except ConnectionRefusedError:
        _bridge_available = False
        _bridge_error = "Connection refused - FreeCAD MCP bridge not running"
    except Exception as e:
        _bridge_available = False
        _bridge_error = f"Cannot connect to FreeCAD MCP bridge: {e}"

    return _bridge_available, _bridge_error


def pytest_collection_modifyitems(
    _config: pytest.Config, items: list[pytest.Item]
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
    is_available, error = _check_bridge_connection()

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
    is_available, error = _check_bridge_connection()
    if not is_available:
        pytest.skip(error or "FreeCAD MCP bridge not available")

    return xmlrpc.client.ServerProxy("http://localhost:9875", allow_none=True)
