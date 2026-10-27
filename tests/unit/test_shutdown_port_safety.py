"""Regression tests for standalone FreeCAD test port preflight."""

import os
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


@pytest.mark.skipif(os.name != "posix", reason="POSIX reuse semantics")
def test_preflight_allows_reusable_time_wait_port() -> None:
    """A closed reusable listener should not be mistaken for an active one."""
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1) as client:
            connection, _ = listener.accept()
            connection.close()
            client.recv(1)
    assert not _is_port_occupied("127.0.0.1", port)
