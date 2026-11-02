"""CAM workbench tools for FreeCAD Robust MCP Server.

These tools build and inspect CAM jobs (stock, tool controllers, operations,
dressups) and post-process them to G-code, without opening any dialog.

They are generic: every operation and dressup type of the CAM workbench is
reachable through ``cam_add_operation``/``cam_add_dressup``, and every option
through ``cam_describe_type``/``cam_get_properties``/``cam_set_properties``,
which read FreeCAD's own property metadata (types, enumerations, tooltips).

The CAM implementation is installed with the FreeCAD bridge. Requests use a
versioned, allowlisted dispatcher inside FreeCAD; an outdated bridge reports
an actionable error without affecting other tools.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from freecad_mcp.tools.utils import wrap_with_transaction

CAM_TIMEOUT_MS = 600_000
CAM_API_VERSION = 1


def build_cam_code(
    func: str,
    args: dict[str, Any],
    transaction: str | None = None,
) -> str:
    """Build a versioned CAM dispatcher call with JSON-encoded arguments."""
    payload = json.dumps(args)
    check = (
        "import json as _json\n"
        "if '_robust_mcp_cam_dispatch' not in globals():\n"
        "    raise RuntimeError('CAM requires an updated Robust MCP Bridge; "
        "install the latest workbench and restart FreeCAD')\n"
    )
    call = (
        f"_result_ = _robust_mcp_cam_dispatch({CAM_API_VERSION!r}, "
        f"{func!r}, _json.loads({payload!r}))\n"
    )
    if transaction:
        doc_name = args.get("doc_name")
        doc_expr = (
            f"FreeCAD.getDocument({doc_name!r})"
            if doc_name
            else "FreeCAD.ActiveDocument"
        )
        call = wrap_with_transaction(call, transaction, doc_expr=doc_expr)
    return check + call


def _drop_none(args: dict[str, Any]) -> dict[str, Any]:
    """Leave out arguments that were not given, so the runtime's defaults apply."""
    return {k: v for k, v in args.items() if v is not None}


def _error_message(result: Any) -> str:
    """Shorten a FreeCAD traceback to its final error line plus the traceback."""
    tb = result.error_traceback or result.stderr or "CAM operation failed"
    last = tb.strip().splitlines()[-1] if tb.strip() else tb
    return f"{last}\n\n{tb}"


def register_cam_tools(mcp: Any, get_bridge: Callable[[], Awaitable[Any]]) -> None:
    """Register CAM workbench tools with the Robust MCP Server.

    Args:
        mcp: The MCPServer instance.
        get_bridge: Async function to get the active bridge.

    Example:
        Register CAM tools with an MCP server::

            from freecad_mcp.tools.cam import register_cam_tools

            register_cam_tools(mcp, get_bridge)
    """

    async def run(
        func: str, args: dict[str, Any], transaction: str | None = None
    ) -> Any:
        """Call the installed bridge's versioned CAM dispatcher."""
        bridge = await get_bridge()
        code = build_cam_code(func, _drop_none(args), transaction)
        result = await bridge.execute_python(code, timeout_ms=CAM_TIMEOUT_MS)
        if result.success:
            return result.result
        detail = result.error_traceback or result.stderr or ""
        last = detail.strip().splitlines()[-1] if detail.strip() else ""
        prefix = "RuntimeError: "
        if last.startswith(prefix):
            message = last.removeprefix(prefix)
            if message.startswith(
                (
                    "Incompatible CAM interface:",
                    "CAM requires an updated Robust MCP Bridge;",
                )
            ):
                raise ToolError(message)
        raise ValueError(_error_message(result))

    @mcp.tool()
    async def cam_get_capabilities() -> dict[str, Any]:
        """List what the CAM workbench offers in the connected FreeCAD.

        Use this first. It reports every operation and dressup type with its
        availability, the enabled post processors, job templates (job_*.json),
        the tool asset path, and known FreeCAD CAM issues the tools detect.

        Returns:
            Dictionary with freecad_version, gui, operations, dressups,
            stock_kinds, post_processors (Job.PostProcessor choices; legacy
            ones on 26.3+), machine_post_processors and machines (26.3+, a
            job uses them through its Machine property), job_templates,
            default_job_template, asset_path, tool_system ("assets" on FreeCAD
            1.1+, "legacy" tool bit files on 1.0), freecad_home,
            known_freecad_issues, stock_materials (26.3+: materials with
            FreeCAD's Machinability model, i.e. the ones CAM offers as stock
            material; name, uuid, library, folder and their generic surface
            speeds, if any).
        """
        return await run("capabilities", {})

    @mcp.tool()
    async def cam_list_tool_library(library: str | None = None) -> dict[str, Any]:
        """List FreeCAD's tool libraries, their tool bits and the tool shapes.

        Tool bits from a library can be used in ``cam_add_tool_controller``
        with ``tool={"library_bit": "<id>"}``. Shapes (endmill, drill, v-bit,
        ...) can be used to define a new bit with ``tool={"shape": ...}``.

        Args:
            library: Only list this library (id or label). All if None.

        Returns:
            Dictionary with libraries (id, label, bits with number, id, label,
            shape, parameters, attributes) and shapes.
        """
        return await run("list_tools", {"library": library})

    @mcp.tool()
    async def cam_analyze_model(
        object_name: str,
        doc_name: str | None = None,
        face_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """List a model's faces and drillable holes, to choose operation Base faces.

        Args:
            object_name: Model object (name or unique label).
            doc_name: Document. Uses the active document if None.
            face_types: Only list these surface types, e.g. ["Plane", "Cylinder"].

        Returns:
            Dictionary with bound_box, volume, valid, faces (face name, surface
            type, area, z range, normal for planes, radius/center/axis for
            cylinders) and drillable_holes (element, diameter, center).
        """
        return await run(
            "analyze_model",
            {
                "object_name": object_name,
                "doc_name": doc_name,
                "face_types": face_types,
            },
        )

    @mcp.tool()
    async def cam_create_job(
        model_objects: list[str],
        doc_name: str | None = None,
        label: str | None = None,
        template: str | None = None,
        model_offset: list[float] | None = None,
        stock: dict[str, Any] | None = None,
        default_tool_controller: bool = True,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a CAM job for one or more model objects, without the job dialog.

        The job works on clones of the models (Job.Model group); the originals
        are not changed. Machine/material defaults belong in a job template
        (see ``cam_export_job_template``).

        Args:
            model_objects: Objects to machine (names or unique labels).
            doc_name: Document. Uses the active document if None.
            label: Job label.
            template: Path to a job_*.json template. None uses FreeCAD's
                default template preference; "" uses no template.
            model_offset: [x, y, z] added to the clones' placement, e.g. to put
                the top of the part at Z0. Stock is then re-created from it.
            stock: Stock definition, same keys as ``cam_set_stock``.
            default_tool_controller: Without a template FreeCAD adds a 5 mm end
                mill tool controller. False removes it.
            properties: Job property values, e.g. {"PostProcessor": "linuxcnc"}.

        Returns:
            The job description from ``cam_inspect_job``.
        """
        return await run(
            "create_job",
            {
                "model_objects": model_objects,
                "doc_name": doc_name,
                "label": label,
                "template": template,
                "model_offset": model_offset,
                "stock": stock,
                "default_tool_controller": default_tool_controller,
                "properties": properties,
            },
            "Create CAM Job",
        )

    @mcp.tool()
    async def cam_set_stock(
        kind: str | None = None,
        job_name: str | None = None,
        doc_name: str | None = None,
        extent_neg: list[float] | None = None,
        extent_pos: list[float] | None = None,
        size: list[float] | None = None,
        radius: float | None = None,
        height: float | None = None,
        placement: dict[str, Any] | None = None,
        material: str | None = None,
    ) -> dict[str, Any]:
        """Replace a job's stock and/or assign the stock material.

        Args:
            kind: "from_base" (model bounding box plus margins), "box" or
                "cylinder". If None: only assign `material` to the existing
                stock, or "from_base" when no material is given.
            job_name: Job. Optional if the document has exactly one job.
            doc_name: Document. Uses the active document if None.
            extent_neg: from_base margins [x, y, z] on the negative sides (mm).
            extent_pos: from_base margins [x, y, z] on the positive sides (mm).
            size: box [length, width, height] (mm).
            radius: cylinder radius (mm).
            height: cylinder height (mm).
            placement: {"base": [x, y, z], "axis": [x, y, z], "angle": deg}.
            material: Stock material (FreeCAD 26.3+), name or UUID of a
                material from cam_get_capabilities' stock_materials. Feeds &
                speeds presets on tool bits are matched against it. A
                replaced stock keeps its material when this is None.

        Returns:
            Dictionary with stock name, kind, bound_box, material,
            material_uuid.
        """
        return await run(
            "set_stock",
            {
                "kind": kind,
                "job_name": job_name,
                "doc_name": doc_name,
                "extent_neg": extent_neg,
                "extent_pos": extent_pos,
                "size": size,
                "radius": radius,
                "height": height,
                "placement": placement,
                "material": material,
            },
            "Set CAM Stock",
        )

    @mcp.tool()
    async def cam_add_tool_controller(
        tool: dict[str, Any],
        job_name: str | None = None,
        doc_name: str | None = None,
        tool_number: int | None = None,
        label: str | None = None,
        spindle_speed: float | None = None,
        spindle_dir: str | None = None,
        horiz_feed: str | None = None,
        vert_feed: str | None = None,
        properties: dict[str, Any] | None = None,
        expressions: dict[str, str | None] | None = None,
        feeds_speeds: str = "preset",
        op_type: str | None = None,
    ) -> dict[str, Any]:
        """Add a tool controller (tool bit plus speeds and feeds) to a job.

        Speeds and feeds come first from FreeCAD's feeds & speeds lookup (the
        tool controller's "Feeds and Speeds Wizard", FreeCAD 26.3+): a preset
        on the tool bit that matches the job's stock material (cam_set_stock
        material). Explicit spindle_speed/horiz_feed/vert_feed/properties
        override it per value.

        Args:
            tool: One of
                {"library_bit": "<bit id from cam_list_tool_library>"},
                {"bit_file": "/path/to/bit.fctb"}, or
                {"shape": "endmill", "name": "6mm EM",
                 "parameters": {"Diameter": "6 mm", "Flutes": 4, ...},
                 "attributes": {...}}.
            job_name: Job. Optional if the document has exactly one job.
            doc_name: Document. Uses the active document if None.
            tool_number: T number. Next free number if None.
            label: Controller label. "TC: <tool label>" if None.
            spindle_speed: Spindle speed in rpm.
            spindle_dir: "Forward", "Reverse" or "None".
            horiz_feed: Feed with unit, e.g. "800 mm/min". A bare number is mm/s.
            vert_feed: Plunge feed with unit, e.g. "200 mm/min".
            properties: Any further tool controller properties.
            expressions: Property expressions, e.g. {"SpindleSpeed": "..."}.
            feeds_speeds: "preset" (only a curated preset of the tool for the
                stock material), "resolver" (FreeCAD's full lookup, which
                falls back to the material's generic surface speed and the
                tool's default chipload) or "none".
            op_type: Narrows the preset choice: "profile", "pocket", "slot",
                "drill", "adaptive" or "surface_finish". None matches any.

        Returns:
            Dictionary with name, label, tool_number, tool, diameter,
            feeds_speeds (what the lookup found and whether it was applied),
            properties.
        """
        return await run(
            "add_tool_controller",
            {
                "tool": tool,
                "job_name": job_name,
                "doc_name": doc_name,
                "tool_number": tool_number,
                "label": label,
                "spindle_speed": spindle_speed,
                "spindle_dir": spindle_dir,
                "horiz_feed": horiz_feed,
                "vert_feed": vert_feed,
                "properties": properties,
                "expressions": expressions,
                "feeds_speeds": feeds_speeds,
                "op_type": op_type,
            },
            "Add Tool Controller",
        )

    @mcp.tool()
    async def cam_feeds_speeds(
        job_name: str | None = None,
        doc_name: str | None = None,
        tool_controllers: list[str] | None = None,
        mode: str = "preset",
        op_type: str | None = None,
        apply: bool = False,
    ) -> dict[str, Any]:
        """Compare tool controllers with FreeCAD's feeds & speeds lookup.

        Runs what the "Feeds and Speeds Wizard" of a tool controller runs
        (FreeCAD 26.3+): presets on the tool bit, matched against the job's
        stock material (cam_set_stock material). Use it to check a job's
        speeds and feeds, or with apply=True to set them.

        Args:
            job_name: Job. Optional if the document has exactly one job.
            doc_name: Document. Uses the active document if None.
            tool_controllers: Tool controllers (names or unique labels). All
                of the job if None.
            mode: "preset" (only curated presets of the tool) or "resolver"
                (also the material's generic surface speed and the tool's
                default chipload).
            op_type: "profile", "pocket", "slot", "drill", "adaptive" or
                "surface_finish"; None matches any.
            apply: Write the suggestion to the tool controller.

        Returns:
            Dictionary with job, material, material_uuid and per tool
            controller: current values and suggestion (source, confidence,
            spindle_speed, horiz_feed_mm_min, vert_feed_mm_min,
            surface_speed_m_min, chipload_mm, warnings, applied, or a note).
        """
        return await run(
            "feeds_speeds",
            {
                "job_name": job_name,
                "doc_name": doc_name,
                "tool_controllers": tool_controllers,
                "mode": mode,
                "op_type": op_type,
                "apply": apply,
            },
            "CAM Feeds and Speeds",
        )

    @mcp.tool()
    async def cam_remove_tool_controller(
        tool_controller: str,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Remove a tool controller (and its tool bit) that no operation uses.

        Args:
            tool_controller: Tool controller (name or unique label).
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with removed (label) and remaining tool controllers.
        """
        return await run(
            "remove_tool_controller",
            {"tool_controller": tool_controller, "doc_name": doc_name},
            "Remove Tool Controller",
        )

    @mcp.tool()
    async def cam_add_operation(
        op_type: str,
        job_name: str | None = None,
        tool_controller: str | None = None,
        base: list[dict[str, Any]] | None = None,
        properties: dict[str, Any] | None = None,
        expressions: dict[str, str | None] | None = None,
        name: str | None = None,
        label: str | None = None,
        doc_name: str | None = None,
        source_operations: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add any CAM operation to a job.

        Use ``cam_get_capabilities`` for the types and ``cam_describe_type``
        for every option of a type. Depth properties are expressions by
        default; giving a value replaces the expression.

        Args:
            op_type: Operation type, e.g. "Profile", "Pocket", "PocketShape",
                "Adaptive", "MillFace", "MillFacing", "Helix", "Drilling",
                "Tapping", "ThreadMilling", "Engrave", "Vcarve", "Deburr",
                "Slot", "Surface", "Waterline", "PlanarSurface",
                "RotarySurface", "Flute", "Probe", "Custom"; or one that works
                on other operations or the program flow: "Comment" (property
                Comment), "Stop" (property Stop: "Mandatory" M0 / "Optional"
                M1), "Copy" (linked copy of one operation), "Array" (linear,
                polar or point array of operations with one tool controller,
                coolant None), "SimpleCopy" (fixed G-code copy). These take no
                tool_controller or base and are appended at the end of the
                job; reorder with cam_set_operation_order.
            job_name: Job. Optional if the document has exactly one job.
            tool_controller: Tool controller (name or label). Required when
                the job has more than one.
            base: Features to machine, [{"object": "<model>", "subelements":
                ["Face3", "Edge7"]}]. Original model names are mapped to the
                job's clones. None keeps FreeCAD's default (e.g. Drilling picks
                all holes, Profile the model outline); [] clears it.
            properties: Property values, e.g. {"Side": "Outside",
                "FinalDepth": -5, "StepDown": "1.5 mm"}.
            expressions: Property expressions; None as value removes one.
            name: Internal object name. The type if None.
            label: Display label.
            doc_name: Document. Uses the active document if None.
            source_operations: Copy, Array, SimpleCopy only: the operations to
                copy or array (names or labels), top-level in the job.

        Returns:
            Dictionary with name, label, type, what was set, and a path summary
            (commands, cut bound box, feeds, cycle time, warnings, notes).
        """
        return await run(
            "add_operation",
            {
                "op_type": op_type,
                "job_name": job_name,
                "tool_controller": tool_controller,
                "base": base,
                "properties": properties,
                "expressions": expressions,
                "name": name,
                "label": label,
                "doc_name": doc_name,
                "source_operations": source_operations,
            },
            f"Add {op_type} Operation",
        )

    @mcp.tool()
    async def cam_add_dressup(
        dressup_type: str,
        base_operation: str,
        properties: dict[str, Any] | None = None,
        expressions: dict[str, str | None] | None = None,
        tag_count: int | None = None,
        label: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Add a dressup to an operation (or to another dressup).

        The dressup replaces the operation in the job. If the connected FreeCAD
        has the known bug where the base operation stays in the job (it would
        be cut twice), the call fails and is undone instead of working around
        it; see ``cam_get_capabilities`` known_freecad_issues.

        Args:
            dressup_type: "Tags", "Boundary", "Dogbone", "Array", "LeadInOut",
                "RampEntry", "Dragknife", "AxisMap", "ZCorrect", and on
                FreeCAD 26.3+ "Boundary2", "Mirror", "PlungeMilling". All but
                the first four need the FreeCAD GUI.
            base_operation: Operation or dressup to dress (name or label).
            properties: Property values, e.g. {"Width": 6, "Height": 1.5}.
            expressions: Property expressions.
            tag_count: Tags only: number of holding tags to generate.
            label: Display label.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with name, label, type, base, what was set and a path
            summary.
        """
        return await run(
            "add_dressup",
            {
                "dressup_type": dressup_type,
                "base_operation": base_operation,
                "properties": properties,
                "expressions": expressions,
                "tag_count": tag_count,
                "label": label,
                "doc_name": doc_name,
            },
            f"Add {dressup_type} Dressup",
        )

    @mcp.tool()
    async def cam_describe_type(
        type_name: str,
        kind: str = "operation",
        groups: list[str] | None = None,
        include_hidden: bool = False,
    ) -> dict[str, Any]:
        """List every option of an operation or dressup type with its defaults.

        Builds the type on a placeholder model in a hidden temporary document,
        reads its properties and closes the document again.

        Args:
            type_name: Operation or dressup type (see cam_get_capabilities).
            kind: "operation" or "dressup".
            groups: Only these property groups, e.g. ["Depth", "Operation"].
            include_hidden: Include properties FreeCAD hides in the editor.

        Returns:
            Dictionary with kind, type and properties (name, type, group,
            default, doc, enum values, expression, read_only).
        """
        return await run(
            "describe_type",
            {
                "type": type_name,
                "kind": kind,
                "groups": groups,
                "include_hidden": include_hidden,
            },
        )

    @mcp.tool()
    async def cam_get_properties(
        object_name: str,
        groups: list[str] | None = None,
        include_hidden: bool = False,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Read all properties of a CAM object with their metadata.

        Works for jobs, stock, setup sheets, tool controllers, operations and
        dressups.

        Args:
            object_name: Object (name or unique label).
            groups: Only these property groups.
            include_hidden: Include properties FreeCAD hides in the editor.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with name, label, kind, type and properties (name, type,
            group, value, doc, enum values, expression, read_only).
        """
        return await run(
            "get_properties",
            {
                "object_name": object_name,
                "groups": groups,
                "include_hidden": include_hidden,
                "doc_name": doc_name,
            },
        )

    @mcp.tool()
    async def cam_set_properties(
        object_name: str,
        values: dict[str, Any] | None = None,
        expressions: dict[str, str | None] | None = None,
        recompute: bool = True,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Set properties of any CAM object, with validation.

        Enumeration values are checked against the allowed list, read-only
        properties are refused, and a plain value replaces an expression.
        Quantities take units: "5 mm", "800 mm/min", "90 °".

        Args:
            object_name: Object (name or unique label).
            values: Property values. Link lists use [{"object", "subelements"}],
                links an object name, vectors [x, y, z].
            expressions: Property expressions; None as value removes one.
            recompute: Recompute the document afterwards.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with what was set and, for operations and dressups, a
            path summary.
        """
        return await run(
            "set_properties",
            {
                "object_name": object_name,
                "values": values,
                "expressions": expressions,
                "recompute": recompute,
                "doc_name": doc_name,
            },
            "Set CAM Properties",
        )

    @mcp.tool()
    async def cam_set_operation_order(
        order: list[str],
        job_name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Reorder the operations of a job (this is the G-code order).

        Args:
            order: Every top-level operation/dressup of the job, in the new order.
            job_name: Job. Optional if the document has exactly one job.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with the new order (labels).
        """
        return await run(
            "set_operation_order",
            {"order": order, "job_name": job_name, "doc_name": doc_name},
            "Reorder CAM Operations",
        )

    @mcp.tool()
    async def cam_inspect_job(
        job_name: str | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Describe a job: models, stock, tool controllers, operations, post.

        Every operation includes a path summary with plausibility warnings
        (no cutting moves, feed 0, rapid moves below the stock top, cuts
        outside the stock) and notes (e.g. cuts below the stock bottom).

        Args:
            job_name: Job. Optional if the document has exactly one job.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with models, stock, tool_controllers, operations,
            setup_sheet, post processor settings, fixtures and cycle_time.
        """
        return await run("inspect_job", {"job_name": job_name, "doc_name": doc_name})

    @mcp.tool()
    async def cam_inspect_path(
        object_name: str,
        gcode_lines: int = 0,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Summarize the toolpath of one operation or dressup.

        Args:
            object_name: Operation or dressup (name or unique label).
            gcode_lines: Also return up to this many lines of its path as
                G-code (FreeCAD internal units: mm, mm/s). 0 returns none.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with commands, by_command, feeds_mm_per_min, cycle_time,
            cut_bound_box, warnings, notes and optionally gcode.
        """
        return await run(
            "inspect_path",
            {
                "object_name": object_name,
                "gcode_lines": gcode_lines,
                "doc_name": doc_name,
            },
        )

    @mcp.tool()
    async def cam_post_process(
        job_name: str | None = None,
        post_processor: str | None = None,
        post_args: str | None = None,
        output_file: str | None = None,
        split_files: bool = True,
        use_job_output: bool = False,
        return_lines: int = 0,
        doc_name: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Post-process a job to G-code and optionally write it to a file.

        If the job names a machine (Job.Machine, FreeCAD 26.3+), the machine
        definition (.fcm in CamAssets/Machines) selects the post processor
        and holds its options, as in FreeCAD's Post Process command; then
        post_processor and post_args must not be given. Otherwise the job's
        legacy post processor runs with "--no-show-editor" added. No dialog
        opens in either case. Check generated G-code in a simulator before
        running it on a machine.

        Args:
            job_name: Job. Optional if the document has exactly one job.
            post_processor: Legacy post processor name, e.g. "linuxcnc_legacy"
                (see cam_get_capabilities). The job's setting if None. Not
                allowed for jobs with a machine.
            post_args: Legacy post processor arguments (replaces the job's
                setting). Not allowed for jobs with a machine.
            output_file: File to write. Nothing is written if None.
            overwrite: Replace an existing explicit output_file when true.
            split_files: When the job splits its output (Job.SplitOutput),
                write one file per section as <name>_<section><ext>.
            use_job_output: Write the files exactly where FreeCAD's Post
                Process command would: folder and names from the job's output
                pattern (Job.PostProcessorOutputFile, e.g. "%D/%S-%t-%d.nc"),
                one file per section when the job splits its output. Existing
                files are overwritten. Not together with output_file. Needs a
                saved document when the pattern uses %D.
            return_lines: Also return up to this many G-code lines.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with machine, post_processor, args, sections, lines,
            files, cycle_time and optionally gcode.
        """
        return await run(
            "post_process",
            {
                "job_name": job_name,
                "post_processor": post_processor,
                "post_args": post_args,
                "output_file": output_file,
                "split_files": split_files,
                "use_job_output": use_job_output,
                "return_lines": return_lines,
                "doc_name": doc_name,
                "overwrite": overwrite,
            },
            "Post Process CAM Job",
        )

    @mcp.tool()
    async def cam_export_job_template(
        file_path: str,
        job_name: str | None = None,
        include_tool_controllers: bool = True,
        include_stock: bool = True,
        include_setup_sheet: bool = True,
        include_post: bool = True,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Save a job's settings as a FreeCAD job template (job_*.json).

        Templates are how FreeCAD keeps machine and material defaults: tool
        controllers with speeds and feeds, setup sheet heights and expressions,
        stock margins and the post processor. Use one with cam_create_job.

        Args:
            file_path: Target file; the name must start with "job_" and end
                with ".json" so FreeCAD finds it.
            job_name: Job. Optional if the document has exactly one job.
            include_tool_controllers: Store the tool controllers.
            include_stock: Store the stock definition.
            include_setup_sheet: Store the setup sheet.
            include_post: Store post processor, arguments and output file.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with file and the stored top-level keys.
        """
        return await run(
            "export_job_template",
            {
                "file_path": file_path,
                "job_name": job_name,
                "include_tool_controllers": include_tool_controllers,
                "include_stock": include_stock,
                "include_setup_sheet": include_setup_sheet,
                "include_post": include_post,
                "doc_name": doc_name,
            },
        )

    @mcp.tool()
    async def cam_check_job(
        job_name: str | None = None,
        report_file: str | None = None,
        images: bool = False,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Run FreeCAD's job check ("Sanity") and optionally write its report.

        The same checks as FreeCAD's CAM Sanity command: tool controllers
        without feed or spindle speed, missing stock material, operations
        without tool, fixtures, and (FreeCAD 26.3+) the machine's post
        processor checks, e.g. spindle speed limits.

        Args:
            job_name: Job. Optional if the document has exactly one job.
            report_file: Write FreeCAD's HTML report to this file.
            images: Embed 3D views in the report (GUI only; opens views).
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with ok (no WARNING/CAUTION), critical (count),
            findings (level NOTE/TIP/WARNING/CAUTION, message, source),
            summary (cycle time, Z range, operations, stock) and report_file.
        """
        return await run(
            "check_job",
            {
                "job_name": job_name,
                "report_file": report_file,
                "images": images,
                "doc_name": doc_name,
            },
        )

    @mcp.tool()
    async def cam_simulate(
        job_name: str | None = None,
        operations: list[str] | None = None,
        resolution: float | None = None,
        compare_with_model: bool = True,
        result_file: str | None = None,
        show_result: bool = False,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Simulate material removal and check for cuts into the part.

        Uses FreeCAD's voxel simulator (the engine of its older CAM
        simulator): the stock is cut along the toolpaths of
        the active operations with their tool shapes, seen from above
        (3-axis; feeds, holder and collisions are not simulated). The
        result is compared with the model's top surface on a grid: material
        removed below the part's surface is reported as a gouge, material
        left above it as material_left_on_part_max. Points closer than two
        grid cells to the part's outline or steps are not judged.

        Args:
            job_name: Job. Optional if the document has exactly one job.
            operations: Only these operations (names or labels), in this
                order. All active ones in job order if None.
            resolution: Voxel size in mm. Default: stock size / 400,
                between 0.05 and 0.5 mm. Smaller is slower.
            compare_with_model: Run the gouge / material left check.
            result_file: Write the simulated stock as a mesh (.stl, .obj).
            show_result: Add the simulated stock to the document as a mesh
                object (and hide the stock in the GUI). Undoable.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with operations, resolution, stock/remaining/removed
            volume, model_check (gouge found, points, area, max depth, worst
            locations; material_left_on_part_max), result_file, result_object.
        """
        return await run(
            "simulate",
            {
                "job_name": job_name,
                "operations": operations,
                "resolution": resolution,
                "compare_with_model": compare_with_model,
                "result_file": result_file,
                "show_result": show_result,
                "doc_name": doc_name,
            },
            "Simulate CAM Job",
        )

    @mcp.tool()
    async def cam_place_model(
        job_name: str | None = None,
        rotate: dict[str, Any] | None = None,
        face_up: dict[str, str] | None = None,
        origin: dict[str, str] | None = None,
        move: list[float] | None = None,
        doc_name: str | None = None,
    ) -> dict[str, Any]:
        """Turn and move the part in a job, e.g. flipped for the second side.

        Works on the job's model clones like FreeCAD's Job dialog (the
        original objects stay where they are). For a second setup, create a
        second job for the same model and place it here. Operations are
        recomputed. A stock "from base" is re-created with the same margins;
        a box or cylinder stock is turned and moved with the part.

        Args:
            job_name: Job. Optional if the document has exactly one job.
            rotate: {"axis": "x"|"y"|"z" or [x, y, z], "angle": degrees},
                around the center of the part's bounding box. Flip:
                {"axis": "x", "angle": 180}.
            face_up: {"object": "<model>", "face": "Face3"}: turn the part so
                this face points up (+Z). Not together with rotate.
            origin: Put the part's bounding box at the origin afterwards:
                {"x": "min"|"max"|"center"|"keep", "y": ...,
                 "z": "top"|"bottom"|"center"|"keep"}; e.g. {"x": "min",
                "y": "min", "z": "top"} for X0 Y0 at the lower left, Z0 on top.
            move: [x, y, z] shift in mm, applied together with origin.
            doc_name: Document. Uses the active document if None.

        Returns:
            Dictionary with rotation, move, model_bound_box, stock_bound_box,
            how the stock was handled and the recomputed operations.
        """
        return await run(
            "place_model",
            {
                "job_name": job_name,
                "rotate": rotate,
                "face_up": face_up,
                "origin": origin,
                "move": move,
                "doc_name": doc_name,
            },
            "Place CAM Model",
        )

    @mcp.tool()
    async def cam_import_tool_library(
        file_path: str,
        library_id: str | None = None,
        label: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Import a tool library file into FreeCAD's tool library store.

        Formats FreeCAD can import: FreeCAD .fctl (its bits are found in the
        stores or in a Bit/ folder next to the Library/ folder) and Camotics
        .json. LinuxCNC .tbl tables can only be exported (FreeCAD has no
        importer). Tool numbers are kept. Camotics tools are stored as
        <library_id>_T<number>.

        Args:
            file_path: The library file.
            library_id: Id (file name) in the store. The file name if None.
            label: Display name. The file's label or the id if None.
            overwrite: Replace an existing library / bits with the same id.

        Returns:
            Dictionary with library, label, format, tools (number, id, label),
            bits_added, bits_already_stored.
        """
        return await run(
            "import_tool_library",
            {
                "file_path": file_path,
                "library_id": library_id,
                "label": label,
                "overwrite": overwrite,
            },
        )

    @mcp.tool()
    async def cam_export_tool_library(
        library: str,
        file_path: str,
    ) -> dict[str, Any]:
        """Write a tool library to a file; the format follows the extension.

        .fctl (FreeCAD), .json (Camotics) or .tbl (LinuxCNC tool table:
        T<n> ... D<diameter> ;label).

        Args:
            library: Library id or label (see cam_list_tool_library).
            file_path: Target file.

        Returns:
            Dictionary with file, format, library and the number of tools.
        """
        return await run(
            "export_tool_library", {"library": library, "file_path": file_path}
        )
