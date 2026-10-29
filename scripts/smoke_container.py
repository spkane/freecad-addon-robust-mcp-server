"""Exercise the MCP protocol in a container, optionally using a real bridge."""

from __future__ import annotations

import argparse
import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check_image(image: str, *, bridge: bool) -> None:
    """Initialize and list tools; call FreeCAD when a bridge is available."""
    args = ["run", "--rm", "-i", "-e", "FREECAD_MODE=xmlrpc"]
    if bridge:
        args.extend(
            [
                "--network=host",
                "-e",
                "FREECAD_SOCKET_HOST=127.0.0.1",
                "-e",
                "FREECAD_BRIDGE_CLIENT_ID",
                "-e",
                "FREECAD_BRIDGE_SECRET",
            ]
        )
    args.append(image)
    parameters = StdioServerParameters(
        command="docker", args=args, env=dict(os.environ)
    )
    async with (
        asyncio.timeout(60),
        stdio_client(parameters) as streams,
        ClientSession(*streams) as session,
    ):
        result = await session.initialize()
        if result.server_info.name != "freecad-mcp":
            raise RuntimeError("Unexpected MCP server identity")
        tools = await session.list_tools()
        if not any(tool.name == "get_freecad_version" for tool in tools.tools):
            raise RuntimeError("FreeCAD version tool is missing")
        if bridge:
            response = await session.call_tool("get_freecad_version")
            if response.is_error:
                raise RuntimeError(f"FreeCAD tool call failed: {response}")
            if not response.structured_content or response.structured_content.get(
                "version"
            ) in (None, "", "unknown"):
                raise RuntimeError("FreeCAD tool did not return a version")


def main() -> None:
    """Run the container smoke test from CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--bridge", action="store_true")
    args = parser.parse_args()
    asyncio.run(check_image(args.image, bridge=args.bridge))


if __name__ == "__main__":
    main()
