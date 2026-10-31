"""Live tests for the CAM tools against the running FreeCAD.

Everything is built from scratch on a plain test part (a block with a pocket
and two through holes) and FreeCAD's built-in tool shapes, so the tests need
no tool library, job template, machine or material of a particular setup.
Features that only newer FreeCAD versions have are checked through
``cam_get_capabilities`` and skipped where FreeCAD lacks them.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from freecad_mcp.tools.cam import register_cam_tools
from tests.integration.auth_support import integration_credentials

pytestmark = pytest.mark.integration

Tools = dict[str, Callable[..., Awaitable[Any]]]

# Block 60 x 40 x 10 mm, top at Z0; pocket 20 x 15 x 4 mm; two 5 mm holes.
_MODEL_CODE = """
import FreeCAD
import Part

doc_name = {doc_name!r}
if doc_name in FreeCAD.listDocuments():
    FreeCAD.closeDocument(doc_name)
doc = FreeCAD.newDocument(doc_name)
block = Part.makeBox(60, 40, 10, FreeCAD.Vector(0, 0, -10))
pocket = Part.makeBox(20, 15, 4, FreeCAD.Vector(10, 12.5, -4))
holes = [
    Part.makeCylinder(2.5, 10, FreeCAD.Vector(x, 20, -10)) for x in (42, 52)
]
shape = block.cut(pocket)
for hole in holes:
    shape = shape.cut(hole)
part = doc.addObject("Part::Feature", "Part")
part.Shape = shape.removeSplitter()
doc.recompute()
_result_ = {{"document": doc.Name, "valid": part.Shape.isValid()}}
"""

_ENDMILL = {
    "shape": "endmill",
    "name": "Test endmill 4 mm",
    "parameters": {
        "Diameter": "4 mm",
        "Flutes": 2,
        "CuttingEdgeHeight": "12 mm",
        "Length": "40 mm",
        "ShankDiameter": "4 mm",
    },
}
_DRILL = {
    "shape": "drill",
    "name": "Test drill 5 mm",
    "parameters": {
        "Diameter": "5 mm",
        "Length": "50 mm",
        "TipAngle": "118 deg",
    },
}


def _register(bridge: XmlRpcBridge) -> Tools:
    """Register the CAM tools against a live bridge, keyed by tool name."""
    mcp = MagicMock()
    tools: Tools = {}

    def tool_decorator() -> Callable[[Any], Any]:
        def wrapper(func: Any) -> Any:
            tools[func.__name__] = func
            return func

        return wrapper

    mcp.tool = tool_decorator

    async def get_bridge() -> XmlRpcBridge:
        return bridge

    register_cam_tools(mcp, get_bridge)
    return tools


@pytest.fixture
async def bridge() -> AsyncIterator[XmlRpcBridge]:
    """A connected XML-RPC bridge."""
    b = XmlRpcBridge(**integration_credentials())
    await b.connect()
    try:
        yield b
    finally:
        await b.disconnect()


@pytest.fixture
async def tools(bridge: XmlRpcBridge) -> Tools:
    """The CAM tools, registered against the live bridge."""
    return _register(bridge)


@pytest.fixture
async def caps(tools: Tools) -> dict[str, Any]:
    """What the connected FreeCAD's CAM workbench offers."""
    result: dict[str, Any] = await tools["cam_get_capabilities"]()
    return result


@pytest.fixture
async def doc(bridge: XmlRpcBridge) -> AsyncIterator[str]:
    """A new document holding the test part; closed afterwards."""
    name = f"McpCam_{uuid4().hex[:12]}"
    result = await bridge.execute_python(_MODEL_CODE.format(doc_name=name))
    assert result.success, result.error_traceback or result.stderr
    assert result.result["valid"] is True
    try:
        yield name
    finally:
        await bridge.execute_python(
            f"if {name!r} in FreeCAD.listDocuments():\n"
            f"    FreeCAD.closeDocument({name!r})\n"
            "_result_ = True\n"
        )


def _version(caps: dict[str, Any]) -> tuple[int, ...]:
    """The connected FreeCAD's version as a tuple, e.g. (1, 1, 4)."""
    return tuple(int(p) for p in caps["freecad_version"].split("."))


def _mm(value: Any) -> float:
    """A length as returned by the tools (number or "5.0 mm") in mm."""
    return float(str(value).split()[0])


def _legacy_post(caps: dict[str, Any]) -> str:
    """The LinuxCNC post processor a job without a machine can use."""
    posts = caps["post_processors"]
    name = next((n for n in ("linuxcnc_legacy", "linuxcnc") if n in posts), None)
    if name is None:
        pytest.skip("no LinuxCNC post processor enabled in this FreeCAD")
    assert name is not None  # pytest.skip() does not return
    return name


async def _job_with_tools(
    tools: Tools, doc: str, drill: bool = False
) -> dict[str, Any]:
    """Create a job without template, an end mill and optionally a drill."""
    job = await tools["cam_create_job"](
        model_objects=["Part"],
        doc_name=doc,
        template="",
        default_tool_controller=False,
        stock={"kind": "from_base", "extent_neg": [2, 2, 0], "extent_pos": [2, 2, 1]},
    )
    endmill = await tools["cam_add_tool_controller"](
        tool=_ENDMILL,
        doc_name=doc,
        tool_number=1,
        spindle_speed=10000,
        horiz_feed="600 mm/min",
        vert_feed="150 mm/min",
        feeds_speeds="none",
    )
    if not drill:
        return {"job": job, "endmill": endmill}
    drill_tc = await tools["cam_add_tool_controller"](
        tool=_DRILL,
        doc_name=doc,
        tool_number=2,
        spindle_speed=3000,
        horiz_feed="100 mm/min",
        vert_feed="100 mm/min",
        feeds_speeds="none",
    )
    return {"job": job, "endmill": endmill, "drill": drill_tc}


async def test_capabilities(caps: dict[str, Any]) -> None:
    """The capability report lists the basic operations and post processors."""
    assert caps["freecad_version"]
    ops = {op["type"]: op["available"] for op in caps["operations"]}
    for op_type in ("Profile", "Pocket", "PocketShape", "Drilling", "MillFace"):
        assert ops.get(op_type) is True, op_type
    dressups = {d["type"] for d in caps["dressups"]}
    assert {"Tags", "Boundary", "Dogbone"} <= dressups
    assert caps["post_processors"]
    assert "known_freecad_issues" in caps


async def test_tool_shapes(tools: Tools) -> None:
    """FreeCAD's built-in tool shapes are listed."""
    result = await tools["cam_list_tool_library"]()
    shapes = {str(s).lower() for s in result["shapes"]}
    assert any("endmill" in s for s in shapes), shapes
    assert any("drill" in s for s in shapes), shapes


async def test_analyze_model(tools: Tools, doc: str) -> None:
    """The model analysis finds the two 5 mm holes and the pocket floor."""
    result = await tools["cam_analyze_model"](object_name="Part", doc_name=doc)
    assert result["valid"] is True
    diameters = sorted(round(h["diameter"], 3) for h in result["drillable_holes"])
    assert diameters == [5.0, 5.0]
    floors = [
        f
        for f in result["faces"]
        if f["surface"] == "Plane" and f["z"] == pytest.approx([-4, -4])
    ]
    assert len(floors) == 1


async def test_job_operations_and_gcode(
    tools: Tools, doc: str, caps: dict[str, Any], tmp_path: Path
) -> None:
    """Job, tool controllers, profile, pocket and drilling post to G-code."""
    setup = await _job_with_tools(tools, doc, drill=True)
    assert setup["endmill"]["tool_number"] == 1
    assert _mm(setup["drill"]["diameter"]) == pytest.approx(5.0)

    analysis = await tools["cam_analyze_model"](object_name="Part", doc_name=doc)
    floor = next(
        f["face"]
        for f in analysis["faces"]
        if f["surface"] == "Plane" and f["z"] == pytest.approx([-4, -4])
    )
    holes = [h["element"] for h in analysis["drillable_holes"]]

    try:
        profile = await tools["cam_add_operation"](
            op_type="Profile",
            doc_name=doc,
            tool_controller=setup["endmill"]["name"],
            properties={"Side": "Outside", "StepDown": "2 mm", "FinalDepth": -10},
        )
    except ValueError as exc:
        # FreeCAD < 26.3 without GUI cannot pick one of several tool
        # controllers; the tool must say so instead of failing obscurely.
        if not caps["gui"] and _version(caps) < (26, 3):
            assert caps["known_freecad_issues"]["tc-console-mode"] in str(exc)
            pytest.skip("FreeCAD bug tc-console-mode, fixed in FreeCAD 26.3")
        raise
    assert profile["path"]["commands"] > 0
    assert not profile["path"]["warnings"], profile["path"]["warnings"]

    pocket = await tools["cam_add_operation"](
        op_type="PocketShape",
        doc_name=doc,
        tool_controller=setup["endmill"]["name"],
        base=[{"object": "Part", "subelements": [floor]}],
        properties={"StepDown": "2 mm"},
    )
    pocket_box = pocket["path"]["cut_bound_box"]
    assert pocket_box[4] == pytest.approx(-4, abs=1e-6)  # z min: pocket floor

    try:
        drilling = await tools["cam_add_operation"](
            op_type="Drilling",
            doc_name=doc,
            tool_controller=setup["drill"]["name"],
            base=[{"object": "Part", "subelements": holes}],
        )
    except ValueError as exc:
        # FreeCAD 1.0 cannot create hole operations from a script.
        if _version(caps) < (1, 1):
            assert caps["known_freecad_issues"]["hole-op-create"] in str(exc)
            pytest.skip("FreeCAD bug hole-op-create, fixed in FreeCAD 1.1")
        raise
    assert drilling["path"]["commands"] > 0

    with pytest.raises(ValueError, match="repeated"):
        await tools["cam_set_operation_order"](
            order=[drilling["name"], pocket["name"], profile["name"], pocket["name"]],
            doc_name=doc,
        )
    order = await tools["cam_set_operation_order"](
        order=[drilling["name"], pocket["name"], profile["name"]], doc_name=doc
    )
    assert order["order"][0] == drilling["label"]

    job = await tools["cam_inspect_job"](doc_name=doc)
    assert [tc["tool_number"] for tc in job["tool_controllers"]] == [1, 2]
    assert len(job["operations"]) == 3

    out = tmp_path / "test.ngc"
    post = await tools["cam_post_process"](
        doc_name=doc,
        post_processor=_legacy_post(caps),
        output_file=str(out),
        split_files=False,
        return_lines=10000,
    )
    gcode = (
        "\n".join(post["gcode"]) if isinstance(post["gcode"], list) else post["gcode"]
    )
    assert "T1" in gcode
    assert "T2" in gcode
    assert any(c in gcode for c in ("G81", "G83", "G73")), "no drill cycle"
    assert out.exists()
    assert out.read_text().strip()


async def test_single_tool_gcode(
    tools: Tools, doc: str, caps: dict[str, Any], tmp_path: Path
) -> None:
    """A one-tool job (profile and pocket) posts to G-code on every version."""
    setup = await _job_with_tools(tools, doc)
    analysis = await tools["cam_analyze_model"](object_name="Part", doc_name=doc)
    floor = next(
        f["face"]
        for f in analysis["faces"]
        if f["surface"] == "Plane" and f["z"] == pytest.approx([-4, -4])
    )
    await tools["cam_add_operation"](
        op_type="PocketShape",
        base=[{"object": "Part", "subelements": [floor]}],
        properties={"StepDown": "2 mm"},
        doc_name=doc,
    )
    profile = await tools["cam_add_operation"](
        op_type="Profile",
        properties={"Side": "Outside", "StepDown": "2 mm", "FinalDepth": -10},
        doc_name=doc,
    )
    assert profile["path"]["cut_bound_box"][4] == pytest.approx(-10, abs=1e-6)

    out = tmp_path / "one_tool.ngc"
    post = await tools["cam_post_process"](
        doc_name=doc,
        post_processor=_legacy_post(caps),
        output_file=str(out),
        split_files=False,
        return_lines=10000,
    )
    gcode = "\n".join(post["gcode"])
    assert setup["endmill"]["tool_number"] == 1
    assert "T1" in gcode
    assert "S10000" in gcode
    assert any(line.startswith(("G1", "G01")) for line in post["gcode"])
    assert out.read_text().strip()


async def test_properties_are_validated(tools: Tools, doc: str) -> None:
    """Enumeration values are checked; describe/get/set round-trip."""
    setup = await _job_with_tools(tools, doc)
    profile = await tools["cam_add_operation"](
        op_type="Profile", doc_name=doc, tool_controller=setup["endmill"]["name"]
    )
    # FreeCAD hides Side until the operation has a Base; ask for all.
    described = await tools["cam_describe_type"](
        type_name="Profile", include_hidden=True
    )
    side = next(p for p in described["properties"] if p["name"] == "Side")
    assert "Outside" in side["enum"]

    with pytest.raises(ValueError, match="Side"):
        await tools["cam_set_properties"](
            object_name=profile["name"], values={"Side": "Sideways"}, doc_name=doc
        )
    await tools["cam_set_properties"](
        object_name=profile["name"], values={"Side": "Inside"}, doc_name=doc
    )
    props = await tools["cam_get_properties"](
        object_name=profile["name"], include_hidden=True, doc_name=doc
    )
    assert next(p for p in props["properties"] if p["name"] == "Side")["value"] == (
        "Inside"
    )


async def test_tags_dressup(tools: Tools, doc: str, caps: dict[str, Any]) -> None:
    """A Tags dressup replaces its profile in the job, or is refused clearly."""
    setup = await _job_with_tools(tools, doc)
    profile = await tools["cam_add_operation"](
        op_type="Profile",
        doc_name=doc,
        tool_controller=setup["endmill"]["name"],
        properties={"Side": "Outside", "FinalDepth": -10},
    )
    try:
        tags = await tools["cam_add_dressup"](
            dressup_type="Tags",
            base_operation=profile["name"],
            tag_count=4,
            doc_name=doc,
        )
    except ValueError as exc:
        # FreeCAD versions without the dressup fix keep the base operation in
        # the job; the tool refuses (and undoes) instead of cutting twice.
        assert caps["known_freecad_issues"]["dressup-base-op"] in str(exc)
        return
    job = await tools["cam_inspect_job"](doc_name=doc)
    top_level = [op["name"] for op in job["operations"]]
    assert tags["name"] in top_level
    assert profile["name"] not in top_level


async def test_place_model(tools: Tools, doc: str) -> None:
    """Placing the part puts its top at Z0 and its corner at the origin."""
    await _job_with_tools(tools, doc)
    result = await tools["cam_place_model"](
        doc_name=doc,
        rotate={"axis": "x", "angle": 180},
        origin={"x": "min", "y": "min", "z": "top"},
    )
    bb = result["model_bound_box"]
    x_min, x_max, y_min, y_max, z_min, z_max = bb
    assert (x_min, y_min, z_max) == pytest.approx((0, 0, 0), abs=1e-6)
    assert (x_max, y_max, z_min) == pytest.approx((60, 40, -10), abs=1e-6)


async def test_check_job(tools: Tools, doc: str) -> None:
    """FreeCAD's job check runs and returns its findings."""
    setup = await _job_with_tools(tools, doc)
    await tools["cam_add_operation"](
        op_type="Profile", doc_name=doc, tool_controller=setup["endmill"]["name"]
    )
    result = await tools["cam_check_job"](doc_name=doc)
    assert isinstance(result["findings"], list)
    assert "ok" in result


async def test_simulate(tools: Tools, doc: str) -> None:
    """The simulation removes material and finds no gouge in a clean job."""
    setup = await _job_with_tools(tools, doc)
    analysis = await tools["cam_analyze_model"](object_name="Part", doc_name=doc)
    floor = next(
        f["face"]
        for f in analysis["faces"]
        if f["surface"] == "Plane" and f["z"] == pytest.approx([-4, -4])
    )
    await tools["cam_add_operation"](
        op_type="PocketShape",
        doc_name=doc,
        tool_controller=setup["endmill"]["name"],
        base=[{"object": "Part", "subelements": [floor]}],
        properties={"StepDown": "2 mm"},
    )
    result = await tools["cam_simulate"](doc_name=doc, resolution=0.5)
    assert result["removed_volume"] > 0
    assert result["model_check"]["gouge"]["found"] is False


@pytest.mark.parametrize("dressup_type", ["LeadInOut", "RampEntry", "Dogbone"])
async def test_more_dressups(
    tools: Tools, doc: str, caps: dict[str, Any], dressup_type: str
) -> None:
    """Dressups work; the GUI-only ones say so clearly without the GUI."""
    setup = await _job_with_tools(tools, doc)
    profile = await tools["cam_add_operation"](
        op_type="Profile",
        doc_name=doc,
        tool_controller=setup["endmill"]["name"],
        properties={"Side": "Outside", "StepDown": "2 mm", "FinalDepth": -10},
    )
    gui_only = dressup_type in ("LeadInOut", "RampEntry")
    if gui_only and not caps["gui"]:
        with pytest.raises(ValueError, match="need the FreeCAD GUI"):
            await tools["cam_add_dressup"](
                dressup_type=dressup_type,
                base_operation=profile["name"],
                doc_name=doc,
            )
        return
    try:
        dressup = await tools["cam_add_dressup"](
            dressup_type=dressup_type, base_operation=profile["name"], doc_name=doc
        )
    except ValueError as exc:
        # FreeCAD without the dressup fix keeps the base operation in the job.
        assert caps["known_freecad_issues"]["dressup-base-op"] in str(exc)
        return
    assert dressup["base"] == profile["name"]
    assert dressup["path"]["commands"] > 0
    job = await tools["cam_inspect_job"](doc_name=doc)
    top_level = [op["name"] for op in job["operations"]]
    assert dressup["name"] in top_level
    assert profile["name"] not in top_level


async def test_stock_kinds(tools: Tools, doc: str) -> None:
    """Box and cylinder stock replace the default stock."""
    await _job_with_tools(tools, doc)
    box = await tools["cam_set_stock"](
        kind="box",
        size=[70, 50, 12],
        placement={"base": [-5, -5, -11]},
        doc_name=doc,
    )
    assert box["bound_box"] == pytest.approx([-5, 65, -5, 45, -11, 1], abs=1e-6)
    cylinder = await tools["cam_set_stock"](
        kind="cylinder", radius=40, height=12, doc_name=doc
    )
    bb = cylinder["bound_box"]
    # with the GUI, OpenCASCADE bounds the displayed (triangulated) cylinder
    assert bb[1] - bb[0] == pytest.approx(80, abs=0.1)
    assert bb[5] - bb[4] == pytest.approx(12, abs=1e-6)


async def test_tool_controller_management(tools: Tools, doc: str) -> None:
    """Feeds & speeds report, removal of an unused controller, path details."""
    setup = await _job_with_tools(tools, doc)
    spare = await tools["cam_add_tool_controller"](
        tool=_ENDMILL, doc_name=doc, label="Spare", feeds_speeds="none"
    )
    assert spare["tool_number"] == 2  # next free number

    report = await tools["cam_feeds_speeds"](doc_name=doc)
    labels = [tc["tool_controller"] for tc in report["tool_controllers"]]
    assert labels == [setup["endmill"]["label"], "Spare"]
    assert report["tool_controllers"][0]["current"]["spindle_speed"] == 10000

    removed = await tools["cam_remove_tool_controller"](
        tool_controller="Spare", doc_name=doc
    )
    assert removed["removed"] == "Spare"
    assert removed["remaining"] == [setup["endmill"]["label"]]

    profile = await tools["cam_add_operation"](
        op_type="Profile",
        properties={"Side": "Outside", "FinalDepth": -10},
        doc_name=doc,
    )
    path = await tools["cam_inspect_path"](
        object_name=profile["name"], gcode_lines=5, doc_name=doc
    )
    assert path["commands"] == profile["path"]["commands"]
    assert len(path["gcode"]) == 5
    assert path["feeds_mm_per_min"] == pytest.approx([150, 600])


async def test_special_operations(tools: Tools, doc: str) -> None:
    """Comment, Stop, Copy and Array operations are added to the job."""
    setup = await _job_with_tools(tools, doc)
    profile = await tools["cam_add_operation"](
        op_type="Profile",
        tool_controller=setup["endmill"]["name"],
        properties={"Side": "Outside", "FinalDepth": -2},
        doc_name=doc,
    )
    comment = await tools["cam_add_operation"](
        op_type="Comment", properties={"Comment": "second part"}, doc_name=doc
    )
    stop = await tools["cam_add_operation"](
        op_type="Stop", properties={"Stop": "Optional"}, doc_name=doc
    )
    copy = await tools["cam_add_operation"](
        op_type="Copy", source_operations=[profile["name"]], doc_name=doc
    )
    assert copy["sources"] == [profile["name"]]
    assert copy["path"]["commands"] == profile["path"]["commands"]
    array = await tools["cam_add_operation"](
        op_type="Array",
        source_operations=[profile["name"]],
        properties={"Type": "Linear1D", "Copies": 1, "Offset": [80, 0, 0]},
        doc_name=doc,
    )
    array_box = array["path"]["cut_bound_box"]
    assert array_box[1] > profile["path"]["cut_bound_box"][1] + 70  # x max

    job = await tools["cam_inspect_job"](doc_name=doc)
    names = [op["name"] for op in job["operations"]]
    assert names == [
        profile["name"],
        comment["name"],
        stop["name"],
        copy["name"],
        array["name"],
    ]


async def test_job_template_round_trip(tools: Tools, doc: str, tmp_path: Path) -> None:
    """A job saved as template creates a job with the same tool controller."""
    await _job_with_tools(tools, doc)
    template = tmp_path / "job_mcp_test.json"
    saved = await tools["cam_export_job_template"](
        file_path=str(template), doc_name=doc
    )
    assert template.exists()
    assert "ToolController" in saved["keys"]

    second = await tools["cam_create_job"](
        model_objects=["Part"], doc_name=doc, template=str(template), label="Again"
    )
    numbers = [tc["tool_number"] for tc in second["tool_controllers"]]
    assert numbers == [1]
    assert second["tool_controllers"][0]["spindle_speed"] == 10000


async def test_tool_library_import_export(
    bridge: XmlRpcBridge, tools: Tools, caps: dict[str, Any], tmp_path: Path
) -> None:
    """A .fctl library with its bit is imported and exported as a .tbl table."""
    root = tmp_path / "Tools"
    (root / "Bit").mkdir(parents=True)
    (root / "Library").mkdir()
    bit_id = f"mcp_test_em_{uuid4().hex[:8]}"
    (root / "Bit" / f"{bit_id}.fctb").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "MCP test endmill 3 mm",
                "shape": "endmill.fcstd",
                "parameter": {
                    "Diameter": "3.0 mm",
                    "CuttingEdgeHeight": "10.0 mm",
                    "Length": "40.0 mm",
                    "ShankDiameter": "3.0 mm",
                    "Flutes": 2,
                },
                "attribute": {},
            }
        )
    )
    library = root / "Library" / "mcp_test.fctl"
    library.write_text(
        json.dumps(
            {
                "version": 1,
                "label": "MCP test",
                "tools": [{"nr": 7, "path": f"{bit_id}.fctb"}],
            }
        )
    )
    lib_id = f"mcp_test_{uuid4().hex[:8]}"
    if caps["tool_system"] != "assets":
        with pytest.raises(ValueError, match=r"FreeCAD 1\.1"):
            await tools["cam_import_tool_library"](
                file_path=str(library), library_id=lib_id
            )
        return

    # The import writes into the asset store of the FreeCAD under test,
    # usually the developer's own; remove both assets again.
    try:
        imported = await tools["cam_import_tool_library"](
            file_path=str(library), library_id=lib_id
        )
        assert [t["number"] for t in imported["tools"]] == [7]

        listed = await tools["cam_list_tool_library"](library=lib_id)
        bits = listed["libraries"][0]["bits"]
        assert [b["number"] for b in bits] == [7]

        table = tmp_path / "mcp_test.tbl"
        exported = await tools["cam_export_tool_library"](
            library=lib_id, file_path=str(table)
        )
        assert exported["tools"] == 1
        text = table.read_text()
        assert "T7" in text
        assert "D3" in text
    finally:
        cleanup = await bridge.execute_python(
            "from Path.Tool import cam_assets\n"
            f"_uris = ({f'toolbitlibrary://{lib_id}'!r}, {f'toolbit://{bit_id}'!r})\n"
            "for _uri in _uris:\n"
            "    if cam_assets.exists(_uri):\n"
            "        cam_assets.delete(_uri)\n"
            "_result_ = [cam_assets.exists(_uri) for _uri in _uris]\n"
        )
        assert cleanup.success, cleanup.error_traceback or cleanup.stderr
        assert cleanup.result == [False, False]
