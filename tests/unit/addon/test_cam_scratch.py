"""Tests for temporary CAM report artifacts."""

import importlib.util
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("embedded", [False, True])
def test_cam_report_scratch_is_under_home_and_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail: bool, embedded: bool
) -> None:
    """Temporary CAM images are contained and cleaned even after an error."""
    module_path = (
        Path(__file__).parents[3]
        / "freecad/RobustMCPBridge/freecad_mcp_bridge/cam_runtime.py"
    )
    monkeypatch.setitem(sys.modules, "FreeCAD", MagicMock(GuiUp=False))
    monkeypatch.syspath_prepend(str(module_path.parent))
    spec = importlib.util.spec_from_file_location("cam_scratch_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    if embedded:
        from freecad_mcp.bridge.private_scratch import private_scratch_directory

        module.__dict__["_embedded_private_scratch_directory"] = (
            private_scratch_directory
        )
        monkeypatch.setitem(sys.modules, "private_scratch", None)
    spec.loader.exec_module(module)
    original_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda path: str(tmp_path) if path == "~" else original_expanduser(path),
    )
    monkeypatch.setattr(module, "_doc", lambda _name: MagicMock())
    monkeypatch.setattr(module, "_job", lambda _doc, _name: SimpleNamespace(Name="Job"))
    seen = []

    def build_image(directory: str) -> object:
        folder = Path(directory)
        assert folder.parent == tmp_path
        seen.append(folder)
        (folder / "preview.png").write_bytes(b"png")
        if fail:
            raise RuntimeError("image creation failed")
        return object()

    class CAMSanity:
        def summarize(self):
            return {"runData": {}, "stockData": {}}

        def get_all_squawks(self):
            return [], []

    for name in ("Path", "Path.Main", "Path.Main.Sanity"):
        package = types.ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    image_module = types.ModuleType("Path.Main.Sanity.ImageBuilder")
    image_module.__dict__.update(
        ImageBuilderFactory=SimpleNamespace(get_image_builder=build_image),
        DummyImageBuilder=object,
    )
    sanity_module = types.ModuleType("Path.Main.Sanity.Sanity")
    sanity_module.__dict__["CAMSanity"] = CAMSanity
    monkeypatch.setitem(sys.modules, image_module.__name__, image_module)
    monkeypatch.setitem(sys.modules, sanity_module.__name__, sanity_module)
    if fail:
        with pytest.raises(RuntimeError, match="image creation failed"):
            module.check_job({"images": True})
    else:
        assert module.check_job({"images": True})["ok"]
    assert seen and not seen[0].exists()
