"""Test the local review policy's defaults and timed bypass boundaries."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def policy_module():
    """Load the policy without a FreeCAD or Qt process."""
    path = Path(__file__).parents[3] / (
        "freecad/RobustMCPBridge/freecad_mcp_bridge/review_policy.py"
    )
    spec = importlib.util.spec_from_file_location("review_policy_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_and_timed_bypass_are_scoped_and_expire(policy_module):
    """An explicit, enabled bypass applies to one action for a bounded time."""
    clock = [100.0]
    policy = policy_module.ReviewPolicy(clock=lambda: clock[0])
    assert policy.requires_review("execute_python")
    with pytest.raises(PermissionError):
        policy.grant_bypass("execute_python", 60)
    policy.set_timed_bypass_enabled(True)
    policy.grant_bypass("execute_python", 60)
    assert not policy.requires_review("execute_python")
    assert policy.requires_review("run_macro")
    policy.grant_bypass("run_macro", 30)
    assert not policy.requires_review("run_macro")
    clock[0] += 30
    assert policy.requires_review("run_macro")
    assert not policy.requires_review("execute_python")
    clock[0] += 30
    assert policy.requires_review("execute_python")


@pytest.mark.parametrize(
    ("platform", "expected"), [("darwin", 10), ("linux", 20), ("win32", 30)]
)
def test_elapsed_clock_selects_platform_clock(
    policy_module, monkeypatch, platform, expected
):
    """Use a sleep-inclusive clock on macOS and Linux when available."""
    monkeypatch.setattr(policy_module, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(
        policy_module,
        "time",
        SimpleNamespace(
            CLOCK_MONOTONIC=10,
            CLOCK_BOOTTIME=20,
            clock_gettime=lambda clock_id: clock_id,
            monotonic=lambda: 30,
        ),
    )
    assert policy_module.elapsed_clock() == expected


def test_bypass_revocation_and_invalid_input_fail_closed(policy_module):
    """Disable, stop and changes to settings revoke transient grants."""
    policy = policy_module.ReviewPolicy()
    policy.set_timed_bypass_enabled(True)
    for value in (0, -1, float("inf"), float("nan"), True, 28801):
        with pytest.raises(ValueError):
            policy.grant_bypass("execute_python", value)
    with pytest.raises(ValueError):
        policy.requires_review("unrecognized")
    policy.grant_bypass("execute_python", 60)
    policy.clear_session()
    assert policy.requires_review("execute_python")
    policy.grant_bypass("execute_python", 60)
    policy.set_timed_bypass_enabled(False)
    assert policy.requires_review("execute_python")
    policy.set_timed_bypass_enabled(True)
    policy.grant_bypass("execute_python", 60)
    policy.configure("execute_python", require_review=True)
    assert policy.requires_review("execute_python")
    policy.configure("execute_python", require_review=False)
    assert not policy.requires_review("execute_python")
