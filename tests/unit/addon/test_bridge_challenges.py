"""Tests for replay-resistant bridge authentication challenges."""

import importlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

ADDON_DIR = Path(__file__).parents[3] / "freecad" / "RobustMCPBridge"


@pytest.fixture
def challenges(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import the standalone workbench package without launching FreeCAD."""
    monkeypatch.syspath_prepend(str(ADDON_DIR))
    return importlib.import_module("freecad_mcp_bridge.challenges")


def test_challenge_is_random_and_single_use(challenges: Any) -> None:
    """A challenge cannot be replayed after its first use."""
    store = challenges.ChallengeStore()
    first = store.issue()
    second = store.issue()
    assert first != second
    assert len(first) >= 43
    assert store.consume(first) is True
    assert store.consume(first) is False
    assert store.consume(second) is True
    assert store.consume("unknown") is False
    assert store.consume([]) is False


def test_expiration_and_pending_limit(challenges: Any) -> None:
    """Expired entries release capacity and cannot be consumed."""
    now = [10.0]
    store = challenges.ChallengeStore(
        max_pending=1, lifetime_seconds=5, clock=lambda: now[0]
    )
    first = store.issue()
    with pytest.raises(RuntimeError, match="Too many"):
        store.issue()
    now[0] = 15.0
    second = store.issue()
    assert store.consume(first) is False
    assert store.consume(second) is True


def test_concurrent_consumers_cannot_replay(challenges: Any) -> None:
    """Only one thread can consume a challenge when requests race."""
    store = challenges.ChallengeStore()
    challenge = store.issue()
    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(store.consume, [challenge] * 32))
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 31


def test_repeated_random_collision_fails_closed(
    challenges: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken random source cannot trap a listener in an endless loop."""
    monkeypatch.setattr(challenges.secrets, "token_urlsafe", lambda _: "a" * 43)
    store = challenges.ChallengeStore()
    store.issue()
    with pytest.raises(RuntimeError, match="unique"):
        store.issue()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_pending": 0},
        {"lifetime_seconds": 0},
        {"lifetime_seconds": float("nan")},
        {"lifetime_seconds": True},
        {"lifetime_seconds": "invalid"},
    ],
)
def test_invalid_limits_are_rejected(challenges: Any, kwargs: dict[str, Any]) -> None:
    """Challenge capacity and lifetime must be positive."""
    with pytest.raises(ValueError, match="positive"):
        challenges.ChallengeStore(**kwargs)
