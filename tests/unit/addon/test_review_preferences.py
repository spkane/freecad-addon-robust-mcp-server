"""Test local review preferences with an isolated parameter store."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def preferences(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load preferences with a fake FreeCAD parameter group."""
    values: dict[str, bool | int] = {}

    class Parameters:
        def GetBool(self, name: str, default: bool) -> bool:
            return bool(values.get(name, default))

        def SetBool(self, name: str, value: bool) -> None:
            values[name] = value

        def GetInt(self, name: str, default: int) -> int:
            return int(values.get(name, default))

        def SetInt(self, name: str, value: int) -> None:
            values[name] = value

    params = Parameters()
    monkeypatch.setitem(
        sys.modules, "FreeCAD", SimpleNamespace(ParamGet=lambda _: params)
    )
    path = Path(__file__).parents[3] / "freecad/RobustMCPBridge/preferences.py"
    spec = importlib.util.spec_from_file_location("review_preferences_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_preferences_default_and_reset(preferences: ModuleType) -> None:
    """Explicit settings persist and reset restores safe defaults."""
    assert preferences.get_review_python() is True
    assert preferences.get_allow_review_bypass() is False
    preferences.set_review_python(False)
    preferences.set_allow_review_bypass(True)
    assert preferences.get_review_python() is False
    assert preferences.get_allow_review_bypass() is True
    preferences.reset_to_defaults()
    assert preferences.get_review_python() is True
    assert preferences.get_allow_review_bypass() is False
