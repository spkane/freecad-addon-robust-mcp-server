"""Verify strong, single-use FreeCAD document identity reservations."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def reservations_module():
    """Load the helper without starting FreeCAD."""
    path = Path(__file__).parents[3] / (
        "freecad/RobustMCPBridge/freecad_mcp_bridge/document_reservations.py"
    )
    spec = importlib.util.spec_from_file_location("document_reservations_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_name_replacement_is_not_the_selected_document(reservations_module):
    """An opaque token retains the selected wrapper through a later review."""
    store = reservations_module.DocumentReservations(2)
    original = object()
    current = {"Model": original}
    token = store.reserve("Model", original)
    guard = store.take(token, "Model", current.__getitem__)
    assert guard()
    current["Model"] = object()
    assert not guard()
    with pytest.raises(ValueError):
        store.take(token, "Model", current.__getitem__)


def test_shutdown_invalidates_claimed_guard(reservations_module):
    """Closing the review registry also invalidates already claimed guards."""
    store = reservations_module.DocumentReservations(1)
    document = object()
    guard = store.take(store.reserve("Model", document), "Model", lambda _: document)
    assert guard()
    store.clear()
    assert not guard()


def test_expired_reservations_release_capacity(reservations_module, monkeypatch):
    """Expired tokens cannot authorize a review and do not fill the registry."""
    clock = [10.0]
    monkeypatch.setattr(
        reservations_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    store = reservations_module.DocumentReservations(1, lifetime=5)
    token = store.reserve("Model", object())
    with pytest.raises(RuntimeError, match="capacity"):
        store.reserve("Other", object())
    clock[0] = 15.0
    with pytest.raises(ValueError, match="unavailable"):
        store.take(token, "Model", lambda _name: None)
    assert store.reserve("Other", object())
    store.clear()
    with pytest.raises(RuntimeError, match="closed"):
        store.reserve("Another", object())


def test_token_cannot_be_rebound_to_another_name(reservations_module):
    """A token presented with another name cannot capture either document."""
    store = reservations_module.DocumentReservations(1)
    token = store.reserve("Model", object())
    with pytest.raises(ValueError, match="unavailable"):
        store.take(token, "Other", lambda _name: None)
    with pytest.raises(ValueError, match="unavailable"):
        store.take(token, "Model", lambda _name: None)


def test_reserve_evicts_expired_entries(reservations_module, monkeypatch):
    """A new reservation recovers capacity without claiming an expired token."""
    clock = [10.0]
    monkeypatch.setattr(
        reservations_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    store = reservations_module.DocumentReservations(1, lifetime=5)
    expired = store.reserve("Model", object())
    clock[0] = 15.0
    document = object()
    token = store.reserve("Other", document)
    assert store.take(token, "Other", lambda _name: document)()
    with pytest.raises(ValueError, match="unavailable"):
        store.take(expired, "Model", lambda _name: None)


def test_discard_unclaimed_is_idempotent_and_does_not_revoke_claimed_guard(
    reservations_module,
):
    """Cleanup releases unused slots but cannot undo a claimed document guard."""
    store = reservations_module.DocumentReservations(1)
    unused = store.reserve("Model", object())
    store.discard(unused)
    store.discard(unused)
    document = object()
    claimed = store.reserve("Model", document)
    guard = store.take(claimed, "Model", lambda _: document)
    store.discard(claimed)
    assert guard()


def test_session_cleanup_only_discards_its_unclaimed_tokens(reservations_module):
    """A closed session cannot invalidate another session or a claimed guard."""
    store = reservations_module.DocumentReservations(3)
    doc = object()
    store.open_owner("first")
    store.open_owner("second")
    abandoned = store.reserve("Model", doc, "first")
    other = store.reserve("Model", doc, "second")
    claimed = store.reserve("Model", doc, "first")
    guard = store.take(claimed, "Model", lambda _: doc)
    store.discard_owner("first")
    with pytest.raises(RuntimeError, match="session is closed"):
        store.reserve("Model", doc, "first")
    with pytest.raises(RuntimeError, match="session is closed"):
        store.open_owner("first")
    with pytest.raises(ValueError, match="unavailable"):
        store.take(abandoned, "Model", lambda _: doc)
    assert store.take(other, "Model", lambda _: doc)()
    assert guard()
