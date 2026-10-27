"""Regression tests for standalone FreeCAD test port preflight."""

import socket

import pytest

from tests.integration.test_shutdown_crash import _is_port_occupied


def test_preflight_detects_unrelated_listener_without_stopping_it() -> None:
    """An unrecognized TCP listener must still block standalone startup."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert _is_port_occupied("127.0.0.1", port)
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


def test_preflight_treats_bind_errors_as_unsafe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unexpected bind failure must not permit standalone startup."""

    def fail_bind(_self: socket.socket, _address: object) -> None:
        raise OSError("bind unavailable")

    monkeypatch.setattr(socket.socket, "bind", fail_bind)
    assert _is_port_occupied()
