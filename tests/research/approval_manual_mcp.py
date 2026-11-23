"""Provide an isolated, harmless MCP client-approval test server over stdio.

The accompanying FreeCAD host probe supplies a private, temporary connection
file. Only one fixed Python example is eligible for local FreeCAD review.
The elicitation tool never executes its input.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import Context, Elicit, MCPServer, Resolve
from pydantic import BaseModel, ConfigDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from freecad_mcp.bridge.authentication import create_hmac_signer
from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.tools.execution import register_execution_tools

EXAMPLE = 'print("Hello from FreeCAD")\n_result_ = 42'


def _form_schema(schema: dict[str, Any]) -> None:
    """Remove object annotations unsupported by some MCP clients."""
    schema.pop("title", None)
    schema.pop("description", None)


class Approval(BaseModel):
    """Explicit approval requested from the MCP client."""

    model_config = ConfigDict(json_schema_extra=_form_schema)

    approved: bool


def question(code: str) -> Elicit[Approval]:
    """Request review of the exact supplied text without executing it."""
    return Elicit("Review this test text (it will not execute):\n" + code, Approval)


class ExampleBridge(SocketBridge):
    """Limit the manual fixture to one harmless reviewed Python example."""

    async def execute_reviewed_python(
        self, code: str, timeout_ms: int | None = None
    ) -> ExecutionResult:
        """Refuse anything other than the documented test expression."""
        if code != EXAMPLE:
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="This test accepts only the documented example code",
                execution_time_ms=0,
                error_type="TestInputRejected",
            )
        return await super().execute_reviewed_python(code, timeout_ms)


def main() -> None:
    """Run the test server using the temporary profile's connection details."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: approval_manual_mcp.py CONNECTION_FILE")
    connection = json.loads(Path(sys.argv[1]).read_text())
    bridge = ExampleBridge(
        host="127.0.0.1",
        port=connection["port"],
        client_id="probe",
        signer=create_hmac_signer(bytes.fromhex(connection["secret"])),
    )

    async def get_bridge() -> Any:
        return bridge

    server = MCPServer("freecad-review-test")
    register_execution_tools(server, get_bridge, allow_unsafe_code=True)

    @server.tool()
    async def elicitation_probe(
        code: str, approval: Annotated[Approval, Resolve(question)]
    ) -> str:
        """Ask the MCP client to display text; this tool never executes it."""
        del code
        return "PROBE_APPROVED" if approval.approved else "PROBE_DENIED"

    @server.tool()
    async def elicitation_direct_probe(code: str, ctx: Context) -> str:
        """Try direct MCP elicitation; never execute the supplied text."""
        if not ctx.session.can_send_request:
            return "PROBE_UNAVAILABLE: direct elicitation has no back-channel"
        result = await ctx.elicit(
            "Review this test text (it will not execute):\n" + code, Approval
        )
        if result.action == "accept" and result.data.approved:
            return "PROBE_APPROVED"
        if result.action == "cancel":
            return "PROBE_CANCELLED"
        return "PROBE_DENIED"

    @server.tool()
    async def elicitation_protocol_probe(ctx: Context) -> str:
        """Report the negotiated MCP protocol version without requesting input."""
        return str(ctx.protocol_version or "unknown")

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
