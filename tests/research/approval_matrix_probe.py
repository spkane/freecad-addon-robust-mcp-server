"""Exercise MCP SDK elicitation using a harmless in-process client and server.

Run with ``uv run python tests/research/approval_matrix_probe.py``. No code is
executed and no FreeCAD connection is made; dispatch is an in-memory marker.
This does not test a real agent's UI or approval policy.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Annotated, Literal

import anyio
from mcp import StdioServerParameters
from mcp.client import Client
from mcp.client.session import ClientRequestContext, ElicitationFnT
from mcp.server.mcpserver import Context, Elicit, MCPServer, Resolve
from mcp.types import ElicitRequestParams, ElicitResult, TextContent, ToolAnnotations
from pydantic import BaseModel

Mode = Literal["legacy", "auto"]
Flow = Literal["resolver", "direct"]
Scenario = Literal[
    "accept",
    "false",
    "decline",
    "cancel",
    "invalid",
    "unsupported",
    "error",
    "timeout",
    "late",
]
CODE = 'print("probe")'
PROBE_PATH = str(Path(__file__).resolve())


class Approval(BaseModel):
    """Explicit response required for the hypothetical action."""

    approved: bool


def question(code: str) -> Elicit[Approval]:
    """Build a full-code elicitation request for the test resolver."""
    return Elicit("Review exact code:\n" + code, Approval)


async def run_case(mode: Mode, flow: Flow, scenario: Scenario) -> None:
    """Exercise one outcome and assert whether the marker is reached."""
    server = MCPServer("harmless-approval-probe")
    events: list[str] = []
    late_responses: list[str] = []
    callback_entered = asyncio.Event()

    @server.tool()
    async def resolver_probe(
        code: str, approval: Annotated[Approval, Resolve(question)]
    ) -> str:
        if not approval.approved:
            return "denied"
        events.append(code)
        return "would execute (probe only)"

    @server.tool()
    async def direct_probe(code: str, ctx: Context) -> str:
        result = await ctx.elicit("Review exact code:\n" + code, Approval)
        if result.action != "accept" or not result.data.approved:
            return "denied"
        events.append(code)
        return "would execute (probe only)"

    async def callback(
        context: ClientRequestContext, params: ElicitRequestParams
    ) -> ElicitResult:
        del context
        assert params.message == "Review exact code:\n" + CODE
        callback_entered.set()
        if scenario == "accept":
            return ElicitResult(action="accept", content={"approved": True})
        if scenario == "false":
            return ElicitResult(action="accept", content={"approved": False})
        if scenario == "invalid":
            return ElicitResult(action="accept", content={})
        if scenario == "error":
            raise RuntimeError("callback failure")
        if scenario == "timeout":
            await asyncio.sleep(5)
        if scenario == "late":
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                with anyio.CancelScope(shield=True):
                    await asyncio.sleep(0.4)
                late_responses.append("accepted")
                return ElicitResult(action="accept", content={"approved": True})
        if scenario == "decline":
            return ElicitResult(action="decline")
        return ElicitResult(action="cancel")

    callback_or_none = None if scenario == "unsupported" else callback
    async with Client(
        server, mode=mode, elicitation_callback=callback_or_none
    ) as client:
        try:
            if scenario in {"timeout", "late"} and (
                mode == "legacy" or flow == "resolver"
            ):
                task = asyncio.create_task(
                    client.call_tool(flow + "_probe", {"code": CODE})
                )
                try:
                    await asyncio.wait_for(callback_entered.wait(), 5)
                    with anyio.fail_after(0.25):
                        result = await task
                finally:
                    if not task.done():
                        task.cancel()
            else:
                with anyio.fail_after(5):
                    result = await client.call_tool(flow + "_probe", {"code": CODE})
                outcome = "error" if result.is_error else "ok"
        except Exception as exc:
            outcome = type(exc).__name__
        if scenario in {"timeout", "late"}:
            await asyncio.sleep(1 if scenario == "late" else 0.1)

    print(f"{mode:6} {flow:8} {scenario:11} {outcome:18} dispatches={len(events)}")
    if scenario == "accept" and (mode == "legacy" or flow == "resolver"):
        assert outcome == "ok" and events == [CODE]
    else:
        assert not events
        if scenario == "late" and (mode == "legacy" or flow == "resolver"):
            assert late_responses == ["accepted"]
        if scenario in {"timeout", "late"} and (mode == "legacy" or flow == "resolver"):
            assert callback_entered.is_set() and outcome == "TimeoutError"
        if (scenario == "false" and (mode == "legacy" or flow == "resolver")) or (
            flow == "direct" and scenario in {"decline", "cancel"} and mode == "legacy"
        ):
            assert outcome == "ok"
        else:
            assert outcome != "ok"


async def main() -> None:
    """Run the matrix against both legacy and modern in-process sessions."""
    logging.disable(logging.CRITICAL)
    modes: list[Mode] = ["legacy", "auto"]
    flows: list[Flow] = ["resolver", "direct"]
    scenarios: list[Scenario] = [
        "accept",
        "false",
        "decline",
        "cancel",
        "invalid",
        "unsupported",
        "error",
        "timeout",
        "late",
    ]
    for mode in modes:
        for flow in flows:
            for scenario in scenarios:
                await run_case(mode, flow, scenario)
    for mode in modes:
        for approved in (True, False):
            server = StdioServerParameters(
                command=sys.executable,
                args=[PROBE_PATH, "--serve"],
            )
            async with Client(
                server, mode=mode, elicitation_callback=make_callback(approved)
            ) as client:
                result = await client.call_tool("resolver_probe", {"code": CODE})
                expected = "PROBE_APPROVED" if approved else "PROBE_DENIED"
                assert not result.is_error
                assert len(result.content) == 1
                assert isinstance(result.content[0], TextContent)
                assert result.content[0].text == expected
                print(f"stdio  {mode:6} approved={approved} {expected}")


def make_callback(approved: bool) -> ElicitationFnT:
    """Return a fixed test response while checking the request's code."""

    async def callback(
        context: ClientRequestContext, params: ElicitRequestParams
    ) -> ElicitResult:
        del context
        assert params.message == "Review exact code:\n" + CODE
        return ElicitResult(action="accept", content={"approved": approved})

    return callback


def serve() -> None:
    """Expose harmless probes over stdio for manual agent-client testing."""
    server = MCPServer("approval-matrix-probe")
    risk = ToolAnnotations(
        read_only_hint=False, destructive_hint=True, open_world_hint=True
    )

    @server.tool(annotations=risk)
    async def resolver_probe(
        code: str, approval: Annotated[Approval, Resolve(question)]
    ) -> str:
        """Request approval of text; never execute it or connect to FreeCAD."""
        del code
        return "PROBE_APPROVED" if approval.approved else "PROBE_DENIED"

    @server.tool(annotations=risk)
    async def direct_probe(code: str, ctx: Context) -> str:
        """Request approval through legacy elicitation; never execute code."""
        result = await ctx.elicit("Review exact code:\n" + code, Approval)
        if result.action == "accept" and result.data.approved:
            return "PROBE_APPROVED"
        return "PROBE_DENIED"

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def read_only_resolver_probe(
        code: str, approval: Annotated[Approval, Resolve(question)]
    ) -> str:
        """Probe elicitation without executing code or changing state."""
        del code
        return "PROBE_APPROVED" if approval.approved else "PROBE_DENIED"

    server.run(transport="stdio")


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve"]:
        serve()
    elif not sys.argv[1:]:
        asyncio.run(main())
    else:
        raise SystemExit("Usage: approval_matrix_probe.py [--serve]")
