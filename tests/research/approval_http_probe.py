"""Exercise harmless MCP elicitation over real loopback streamable HTTP.

Run with ``uv run python tests/research/approval_http_probe.py``. This uses a
synthetic SDK client, never runs supplied code, and stops its own server.
"""

import asyncio
import multiprocessing
import queue
import socket
from typing import Annotated, Any, Literal

import anyio
from mcp.client import Client
from mcp.client.session import ClientRequestContext, ElicitationFnT
from mcp.server.mcpserver import Elicit, MCPServer, Resolve
from mcp.types import ElicitRequestParams, ElicitResult
from pydantic import BaseModel

CODE = 'print("http probe")'
Mode = Literal["legacy", "auto"]
Scenario = Literal[
    "accept", "false", "decline", "cancel", "invalid", "unsupported", "late"
]


class Approval(BaseModel):
    """Require an explicit affirmative answer."""

    approved: bool


def question(code: str) -> Elicit[Approval]:
    """Describe the exact text sent for review."""
    return Elicit("Review exact code: " + code, Approval)


def serve(port: int, dispatches: Any) -> None:
    """Serve a probe that only emits a marker when approved."""
    app = MCPServer("approval-http-probe")

    @app.tool()
    async def probe(code: str, approval: Annotated[Approval, Resolve(question)]) -> str:
        if not approval.approved:
            return "DENIED"
        dispatches.put(code)
        return "APPROVED"

    app.run("streamable-http", host="127.0.0.1", port=port)


def make_callback(scenario: Scenario, late_attempts: list[str]) -> ElicitationFnT:
    """Make a synthetic response, including a post-cancellation response."""

    async def callback(
        context: ClientRequestContext, params: ElicitRequestParams
    ) -> ElicitResult:
        del context
        assert params.message == "Review exact code: " + CODE
        if scenario == "accept":
            return ElicitResult(action="accept", content={"approved": True})
        if scenario == "false":
            return ElicitResult(action="accept", content={"approved": False})
        if scenario == "invalid":
            return ElicitResult(action="accept", content={})
        if scenario == "late":
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                with anyio.CancelScope(shield=True):
                    await asyncio.sleep(0.4)
                late_attempts.append("accepted")
                return ElicitResult(action="accept", content={"approved": True})
        if scenario == "decline":
            return ElicitResult(action="decline")
        return ElicitResult(action="cancel")

    return callback


async def run_case(port: int, dispatches: Any, mode: Mode, scenario: Scenario) -> None:
    """Check the result and whether the server dispatched after each case."""
    late_attempts: list[str] = []
    callback = (
        None if scenario == "unsupported" else make_callback(scenario, late_attempts)
    )
    async with Client(
        f"http://127.0.0.1:{port}/mcp", mode=mode, elicitation_callback=callback
    ) as client:
        try:
            with anyio.fail_after(0.25 if scenario == "late" else 5):
                result = await client.call_tool("probe", {"code": CODE})
                outcome = "error" if result.is_error else str(result.model_dump())
        except Exception as exc:
            outcome = type(exc).__name__
        if scenario == "late":
            await asyncio.sleep(1)
    if scenario == "accept":
        marker = await asyncio.to_thread(dispatches.get, True, 2)
        assert marker == CODE and "APPROVED" in outcome
    else:
        try:
            marker = await asyncio.to_thread(dispatches.get, True, 0.2)
        except queue.Empty:
            marker = None
        assert marker is None, (mode, scenario, marker)
        if scenario == "late":
            assert late_attempts == ["accepted"]
        if scenario == "false":
            assert "DENIED" in outcome
        else:
            assert "APPROVED" not in outcome
    print(f"http {mode:6} {scenario:11} {outcome[:80]}", flush=True)


async def run_concurrent(port: int, dispatches: Any, mode: Mode) -> None:
    """Ensure decisions on separate sessions do not authorize each other."""

    async def call(code: str, approved: bool) -> None:
        async def callback(
            context: ClientRequestContext, params: ElicitRequestParams
        ) -> ElicitResult:
            del context
            assert params.message == "Review exact code: " + code
            await asyncio.sleep(0.1)
            return ElicitResult(action="accept", content={"approved": approved})

        async with Client(
            f"http://127.0.0.1:{port}/mcp", mode=mode, elicitation_callback=callback
        ) as client:
            result = await client.call_tool("probe", {"code": code})
            assert ("APPROVED" if approved else "DENIED") in str(result.model_dump())

    await asyncio.gather(call("approved request", True), call("denied request", False))
    assert await asyncio.to_thread(dispatches.get, True, 2) == "approved request"
    try:
        unexpected = await asyncio.to_thread(dispatches.get, True, 0.2)
    except queue.Empty:
        unexpected = None
    assert unexpected is None
    print(f"http {mode:6} concurrent decisions remained isolated", flush=True)


async def main() -> None:
    """Run the matrix, always terminating and reaping the owned server."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    dispatches: Any = multiprocessing.Queue()
    proc = multiprocessing.Process(target=serve, args=(port, dispatches))
    proc.start()
    try:
        for _ in range(50):
            try:
                _reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise RuntimeError("HTTP server did not start")
        modes: list[Mode] = ["legacy", "auto"]
        scenarios: list[Scenario] = [
            "accept",
            "false",
            "decline",
            "cancel",
            "invalid",
            "unsupported",
            "late",
        ]
        for mode in modes:
            for scenario in scenarios:
                await run_case(port, dispatches, mode, scenario)
            await run_concurrent(port, dispatches, mode)
    finally:
        proc.terminate()
        await asyncio.to_thread(proc.join, 3)
        if proc.is_alive():
            proc.kill()
            await asyncio.to_thread(proc.join)
        dispatches.close()
        dispatches.join_thread()


if __name__ == "__main__":
    asyncio.run(main())
