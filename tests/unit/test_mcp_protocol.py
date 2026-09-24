"""Protocol-level regression tests for the MCP server."""

import asyncio
import os
import socket
import sys
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast
from xmlrpc.server import SimpleXMLRPCServer

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


def _execute_freecad_code(code: str) -> dict[str, Any]:
    """Return minimal FreeCAD-compatible results for bridge calls."""
    result: Any = True
    if "FreeCAD.Version" in code:
        result = {
            "version": "1.0.2",
            "version_tuple": [1, 0, 2],
            "build_date": "test",
            "python_version": sys.version,
            "gui_available": False,
        }
    return {
        "success": True,
        "result": result,
        "stdout": "",
        "stderr": "",
    }


@contextmanager
def _fake_xmlrpc_server() -> Iterator[int]:
    """Run a minimal local XML-RPC bridge and yield its assigned port."""
    server = SimpleXMLRPCServer(
        ("127.0.0.1", 0),
        allow_none=True,
        logRequests=False,
    )
    server.register_function(cast("Any", _execute_freecad_code), "execute")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _server_environment(xmlrpc_port: int) -> dict[str, str]:
    """Build the environment for an MCP server using the fake bridge."""
    return {
        **os.environ,
        "FREECAD_MODE": "xmlrpc",
        "FREECAD_SOCKET_HOST": "127.0.0.1",
        "FREECAD_XMLRPC_PORT": str(xmlrpc_port),
        "FREECAD_TRANSPORT": "stdio",
    }


def _available_tcp_port() -> int:
    """Ask the operating system for a currently available loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        return cast("int", port_socket.getsockname()[1])


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    """Stop a protocol-test server process without leaving a child behind."""
    if process.returncode is not None:
        await process.wait()
        return

    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except TimeoutError:
        process.kill()
        await process.wait()


async def _start_streamable_http_server(
    xmlrpc_port: int,
) -> tuple[asyncio.subprocess.Process, int]:
    """Start the HTTP test server, retrying an early port-bind failure."""
    attempts = 3
    return_codes: list[int] = []

    for _ in range(attempts):
        http_port = _available_tcp_port()
        environment = {
            **_server_environment(xmlrpc_port),
            "FREECAD_TRANSPORT": "http",
            "FREECAD_HTTP_PORT": str(http_port),
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "freecad_mcp.server",
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        for _ in range(50):
            if process.returncode is not None:
                return_codes.append(process.returncode)
                await process.wait()
                break
            try:
                with socket.create_connection(("127.0.0.1", http_port), timeout=0.1):
                    return process, http_port
            except OSError:
                await asyncio.sleep(0.1)
        else:
            await _stop_process(process)
            pytest.fail("Streamable HTTP server did not start")

    raise AssertionError(
        "Streamable HTTP server exited before readiness after "
        f"{attempts} port-allocation attempts (return codes: {return_codes})"
    )


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_stdio_first_tool_call_completes() -> None:
    """Initialize, list tools, and complete a first call over MCP stdio."""
    with _fake_xmlrpc_server() as xmlrpc_port:
        server_parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "freecad_mcp.server"],
            env=_server_environment(xmlrpc_port),
        )
        with tempfile.TemporaryFile(mode="w+") as stderr:
            async with stdio_client(server_parameters, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    initialize_result = await session.initialize()
                    tools_result = await session.list_tools()
                    call_result = await session.call_tool("get_freecad_version")

        assert initialize_result.server_info.name == "freecad-mcp"
        assert initialize_result.server_info.version
        assert any(tool.name == "get_freecad_version" for tool in tools_result.tools)
        assert call_result.is_error is False


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_streamable_http_first_tool_call_completes() -> None:
    """Initialize, list tools, and complete a first call over Streamable HTTP."""
    with _fake_xmlrpc_server() as xmlrpc_port:
        process, http_port = await _start_streamable_http_server(xmlrpc_port)

        try:
            for _ in range(50):
                try:
                    with socket.create_connection(
                        ("127.0.0.1", http_port), timeout=0.1
                    ):
                        break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                pytest.fail("Streamable HTTP server did not start")

            async with streamable_http_client(
                f"http://127.0.0.1:{http_port}/mcp"
            ) as streams:
                async with ClientSession(*streams[:2]) as session:
                    initialize_result = await session.initialize()
                    tools_result = await session.list_tools()
                    call_result = await session.call_tool("get_freecad_version")

            assert initialize_result.server_info.name == "freecad-mcp"
            assert any(
                tool.name == "get_freecad_version" for tool in tools_result.tools
            )
            assert call_result.is_error is False
        finally:
            await _stop_process(process)
