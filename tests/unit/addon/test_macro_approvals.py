"""Test exact macro approvals without needing a FreeCAD installation."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def approvals(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the standalone policy module with no FreeCAD dependencies."""
    path = (
        Path(__file__).parents[3]
        / "freecad/RobustMCPBridge/freecad_mcp_bridge/macro_approvals.py"
    )
    spec = importlib.util.spec_from_file_location("macro_approvals_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_approval_is_bound_to_path_and_content(
    approvals: ModuleType, tmp_path: Path
) -> None:
    """Changing either the file path or its bytes requires a fresh decision."""
    storage = [""]
    store = approvals.MacroApprovalStore(
        lambda: storage[0], lambda v: storage.__setitem__(0, v)
    )
    first = approvals.MacroApproval(str(tmp_path / "first.FCMacro"), "a" * 64)
    changed = approvals.MacroApproval(first.path, "b" * 64)
    other_path = approvals.MacroApproval(str(tmp_path / "other.FCMacro"), first.sha256)
    assert store.entries() == ()
    store.add(first)
    store.add(first)
    assert store.entries() == (first,)
    assert store.contains(first)
    assert not store.contains(changed)
    assert not store.contains(other_path)
    store.add(changed)
    assert store.remove(first)
    assert not store.contains(first)
    assert store.contains(changed)
    assert not store.remove(first)
    reopened = approvals.MacroApprovalStore(
        lambda: storage[0], lambda v: storage.__setitem__(0, v)
    )
    assert reopened.entries() == (changed,)


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"version": true, "approvals": []}',
        '{"version": 1, "approvals": [{}]}',
    ],
)
def test_invalid_saved_state_fails_closed(approvals: ModuleType, raw: str) -> None:
    """Corrupt saved data is never treated as an authorization."""
    store = approvals.MacroApprovalStore(lambda: raw, lambda _value: None)
    with pytest.raises(ValueError):
        store.entries()


def test_corrupt_approvals_can_be_cleared(approvals: ModuleType) -> None:
    """A local reset revokes invalid data without attempting to parse it."""
    storage = ["broken"]
    store = approvals.MacroApprovalStore(
        lambda: storage[0], lambda value: storage.__setitem__(0, value)
    )
    with pytest.raises(ValueError):
        store.entries()
    store.clear()
    assert store.entries() == ()


def test_rejects_duplicate_or_invalid_records(
    approvals: ModuleType, tmp_path: Path
) -> None:
    """Only absolute paths and full lowercase SHA-256 digests are accepted."""
    with pytest.raises(ValueError):
        approvals.MacroApproval("relative.FCMacro", "a" * 64)
    with pytest.raises(ValueError):
        approvals.MacroApproval(str(tmp_path / "macro"), "A" * 64)
    item = {"path": str(tmp_path / "macro"), "sha256": "a" * 64}
    raw = json.dumps({"version": 1, "approvals": [item, item]})
    store = approvals.MacroApprovalStore(lambda: raw, lambda _value: None)
    with pytest.raises(ValueError, match="Duplicate"):
        store.entries()


def test_write_failure_does_not_grant_approval(
    approvals: ModuleType, tmp_path: Path
) -> None:
    """A failed persistence write must not create an in-memory approval."""

    def fail(_value: str) -> None:
        raise OSError("write failed")

    store = approvals.MacroApprovalStore(lambda: "", fail)
    item = approvals.MacroApproval(str(tmp_path / "macro"), "a" * 64)
    with pytest.raises(OSError):
        store.add(item)
    assert not store.contains(item)
