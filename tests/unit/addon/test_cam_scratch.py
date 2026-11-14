"""Tests for temporary CAM report artifacts."""

import importlib.util
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("embedded", [False, True])
@pytest.mark.parametrize("explicit_report", [False, True])
def test_cam_report_scratch_is_under_home_and_removed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail: bool,
    embedded: bool,
    explicit_report: bool,
) -> None:
    """Temporary images are cleaned; explicit report destinations are preserved."""
    module_path = (
        Path(__file__).parents[3]
        / "freecad/RobustMCPBridge/freecad_mcp_bridge/cam_runtime.py"
    )
    monkeypatch.setitem(sys.modules, "FreeCAD", MagicMock(GuiUp=False))
    monkeypatch.syspath_prepend(str(module_path.parent))
    spec = importlib.util.spec_from_file_location("cam_scratch_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    def unexpected_scratch(_prefix):
        raise AssertionError("Explicit reports must not create scratch space")

    if embedded:
        from freecad_mcp.bridge.private_scratch import private_scratch_directory

        module.__dict__["_embedded_private_scratch_directory"] = (
            unexpected_scratch if explicit_report else private_scratch_directory
        )
        monkeypatch.setitem(sys.modules, "private_scratch", None)
    elif explicit_report:
        monkeypatch.setitem(
            sys.modules,
            "private_scratch",
            SimpleNamespace(private_scratch_directory=unexpected_scratch),
        )
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
        if explicit_report:
            assert folder == tmp_path
        else:
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

        def get_output_report(self):
            return "report"

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
    args: dict[str, Any] = {"images": True}
    if explicit_report:
        args["report_file"] = str(tmp_path / "report.html")
    if fail:
        with pytest.raises(RuntimeError, match="image creation failed"):
            module.check_job(args)
    else:
        assert module.check_job(args)["ok"]
    assert seen
    if explicit_report:
        assert seen[0] == tmp_path
        if not fail:
            assert (tmp_path / "report.html").read_text() == "report"
    else:
        assert not seen[0].exists()
