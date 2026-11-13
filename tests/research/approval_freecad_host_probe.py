"""Exercise local review in an isolated installed FreeCAD GUI profile.

The probe programmatically accepts and denies harmless requests. It does not
verify what an interactive human or MCP client sees. It owns only the child
process it launches and uses a disposable profile with a test-only credential.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def serve_http(http_port: int, bridge_port: int) -> None:
    """Serve the actual execution tool on a disposable loopback endpoint."""
    from approval_manual_mcp import ExampleBridge
    from mcp.server.mcpserver import MCPServer

    from freecad_mcp.bridge.authentication import create_hmac_signer
    from freecad_mcp.tools.execution import register_execution_tools

    bridge = ExampleBridge(
        host="127.0.0.1",
        port=bridge_port,
        client_id="probe",
        signer=create_hmac_signer(b"x" * 32),
    )

    async def get_bridge():
        return bridge

    server = MCPServer("real-freecad-review-http-probe")
    register_execution_tools(server, get_bridge, allow_unsafe_code=True)
    server.run("streamable-http", host="127.0.0.1", port=http_port)


async def exercise_http(bridge_port: int) -> None:
    """Test legacy and modern MCP HTTP sessions against the live bridge."""
    from mcp.client import Client
    from mcp.types import TextContent

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        http_port = listener.getsockname()[1]
    process = multiprocessing.get_context("spawn").Process(
        target=serve_http, args=(http_port, bridge_port)
    )
    process.start()
    try:
        for _ in range(100):
            try:
                _reader, writer = await asyncio.open_connection("127.0.0.1", http_port)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise RuntimeError("MCP HTTP probe did not start")
        for mode, approved in (("legacy", True), ("auto", False)):
            async with Client(f"http://127.0.0.1:{http_port}/mcp", mode=mode) as client:
                result = await asyncio.wait_for(
                    client.call_tool(
                        "execute_python",
                        {"code": 'print("Hello from FreeCAD")\n_result_ = 42'},
                    ),
                    20,
                )
                if (
                    result.is_error
                    or not result.content
                    or not isinstance(result.content[0], TextContent)
                ):
                    raise RuntimeError("MCP HTTP tool call failed")
                payload = json.loads(result.content[0].text)
                if payload["success"] is not approved:
                    raise RuntimeError(f"Unexpected MCP HTTP result: {payload}")
                if approved and payload["result"] != 42:
                    raise RuntimeError(f"Unexpected execution result: {payload}")
                if not approved and (
                    payload["error_type"] != "ReviewDenied" or payload["stdout"]
                ):
                    raise RuntimeError(f"Unexpected denial result: {payload}")
    finally:
        process.terminate()
        await asyncio.to_thread(process.join, 3)
        if process.is_alive():
            process.kill()
            await asyncio.to_thread(process.join)


async def exercise_mcp(port: int, profile: Path) -> None:
    """Call the actual MCP tool over stdio against the live bridge."""
    from mcp import StdioServerParameters
    from mcp.client import Client
    from mcp.types import TextContent

    connection = profile / "connection.json"
    fd = os.open(connection, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump({"port": port, "secret": "78" * 32}, stream)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("approval_manual_mcp.py")), str(connection)],
    )
    async with Client(parameters) as client:
        for approved in (True, False):
            code = 'print("Hello from FreeCAD")\n_result_ = 42'
            result = await asyncio.wait_for(
                client.call_tool("execute_python", {"code": code}), 20
            )
            if (
                result.is_error
                or not result.content
                or not isinstance(result.content[0], TextContent)
            ):
                raise RuntimeError("MCP tool call failed")
            payload = json.loads(result.content[0].text)
            if payload["success"] is not approved:
                raise RuntimeError(f"Unexpected MCP tool result: {payload}")
            if approved and payload["result"] != 42:
                raise RuntimeError(f"Unexpected execution result: {payload}")
            if not approved and (
                payload["error_type"] != "ReviewDenied" or payload["stdout"]
            ):
                raise RuntimeError(f"Unexpected denial result: {payload}")


def main() -> None:  # noqa: PLR0912
    """Run the host probe and clean up the process and profile on any failure."""
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", help="Path to the installed FreeCAD GUI executable")
    parser.add_argument("--screenshot", type=Path, help="Save the test dialog image")
    parser.add_argument("--mcp", action="store_true", help="Exercise an MCP SDK client")
    parser.add_argument("--mcp-http", action="store_true", help="Exercise MCP HTTP")
    parser.add_argument(
        "--preferences", action="store_true", help="Exercise the real preferences panel"
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Keep an isolated profile for client testing",
    )
    args = parser.parse_args()
    if sum((args.manual, args.mcp, args.mcp_http)) > 1:
        parser.error("Choose only one of --manual, --mcp and --mcp-http")
    if args.manual and args.screenshot:
        parser.error("--manual cannot be combined with --screenshot")
    if args.preferences and args.manual:
        parser.error("--preferences cannot be combined with --manual")
    if args.preferences and (args.mcp or args.mcp_http):
        parser.error("--preferences cannot be combined with --mcp or --mcp-http")
    project = Path(__file__).resolve().parents[2]
    macro = Path(__file__).with_name("approval_freecad_host.FCMacro")
    with tempfile.TemporaryDirectory(prefix="freecad-review-host-") as temp:
        profile = Path(temp)
        (profile / "data").mkdir()
        (profile / "temp").mkdir()
        result_path = profile / "result.json"
        env = os.environ.copy()
        env.update(
            FREECAD_USER_DATA=str(profile / "data"),
            TMPDIR=str(profile / "temp"),
            FREECAD_MCP_TESTING="1",
            MCP_REVIEW_PROBE_ADDON=str(project / "freecad" / "RobustMCPBridge"),
            MCP_REVIEW_PROBE_RESULT=str(result_path),
        )
        if args.screenshot:
            env["MCP_REVIEW_PROBE_SCREENSHOT"] = str(profile / "review.png")
        if args.preferences:
            env["MCP_REVIEW_PROBE_PREFERENCES"] = "1"
        if args.mcp or args.mcp_http or args.manual:
            env["MCP_REVIEW_PROBE_PORT"] = str(profile / "port")
            env["MCP_REVIEW_PROBE_DONE"] = str(profile / "done")
        if args.manual:
            env["MCP_REVIEW_PROBE_MANUAL"] = "1"
            env["MCP_REVIEW_PROBE_SECRET"] = secrets.token_hex(32)
        command = [
            args.binary,
            "--user-cfg",
            str(profile / "user.cfg"),
            "--system-cfg",
            str(profile / "system.cfg"),
            str(macro),
        ]
        process = subprocess.Popen(  # noqa: S603 - binary is selected by the tester
            command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            if args.mcp or args.mcp_http or args.manual:
                deadline = time.monotonic() + 25
                while not (profile / "port").is_file() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("FreeCAD exited before opening the bridge")
                    time.sleep(0.05)
                if not (profile / "port").is_file():
                    raise RuntimeError("FreeCAD did not open the bridge in time")
                port = int((profile / "port").read_text())
                if args.manual:
                    connection = profile / "connection.json"
                    fd = os.open(
                        connection, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                    )
                    with os.fdopen(fd, "w") as stream:
                        json.dump(
                            {"port": port, "secret": env["MCP_REVIEW_PROBE_SECRET"]},
                            stream,
                        )
                    server = Path(__file__).with_name("approval_manual_mcp.py")
                    command = [sys.executable, str(server), str(connection)]
                    client_config = profile / "claude-mcp.json"
                    client_config.write_text(
                        json.dumps(
                            {
                                "mcpServers": {
                                    "freecad_review_probe": {
                                        "command": command[0],
                                        "args": command[1:],
                                    }
                                }
                            }
                        )
                    )
                    client_config.chmod(0o600)
                    codex_command = [
                        "codex",
                        "-c",
                        "mcp_servers.freecad_review_probe.command="
                        + json.dumps(command[0]),
                        "-c",
                        "mcp_servers.freecad_review_probe.args="
                        + json.dumps(command[1:]),
                    ]
                    print(
                        "Isolated FreeCAD is running. In another terminal, start a client:",
                        flush=True,
                    )
                    print(
                        "Use the commands below for this test; your normal FreeCAD "
                        "MCP configuration points to a different bridge.",
                        flush=True,
                    )
                    print("  " + shlex.join(codex_command), flush=True)
                    print(
                        "  "
                        + shlex.join(
                            [
                                "claude",
                                "--mcp-config",
                                str(client_config),
                                "--strict-mcp-config",
                            ]
                        ),
                        flush=True,
                    )
                    print(
                        "Ask the client to call execute_python with exactly:",
                        flush=True,
                    )
                    print('print("Hello from FreeCAD")\n_result_ = 42', flush=True)
                    print(
                        "For client-side prompts, call elicitation_probe with test text; "
                        "it never executes its input.",
                        flush=True,
                    )
                    print(
                        "For comparison, elicitation_direct_probe uses direct MCP "
                        "elicitation and elicitation_protocol_probe reports the protocol.",
                        flush=True,
                    )
                    print(
                        "Try Allow once, Deny, and closing the dialog on separate calls.",
                        flush=True,
                    )
                    print(
                        "Close FreeCAD or press Ctrl-C here to end the isolated session.",
                        flush=True,
                    )
                    try:
                        process.wait()
                    except KeyboardInterrupt:
                        print("Stopping the isolated FreeCAD session.", flush=True)
                    return
                try:
                    if args.mcp_http:
                        asyncio.run(exercise_http(port))
                    else:
                        asyncio.run(exercise_mcp(port, profile))
                finally:
                    (profile / "done").touch()
            try:
                process.wait(timeout=45)
            except subprocess.TimeoutExpired as error:
                raise RuntimeError("FreeCAD host probe timed out") from error
            if process.returncode != 0 or not result_path.is_file():
                raise RuntimeError(
                    f"FreeCAD host probe failed: exit {process.returncode}"
                )
            result = json.loads(result_path.read_text())
            expected = (
                ["approved", "approved", "denied"]
                if args.preferences
                else ["approved", "denied"]
            )
            if result.get("errors") or result.get("results") != expected:
                raise RuntimeError(f"FreeCAD review probe failed: {result}")
            if args.preferences and result.get("preferences_tested") is not True:
                raise RuntimeError(f"FreeCAD preferences probe failed: {result}")
            if args.preferences and result.get("seen") != 2:
                raise RuntimeError(
                    f"Timed bypass did not skip exactly one dialog: {result}"
                )
            if args.screenshot:
                screenshot = profile / "review.png"
                if not screenshot.is_file():
                    raise RuntimeError("Review dialog screenshot was not captured")
                shutil.copyfile(screenshot, args.screenshot)
            print(
                f"FreeCAD host approval and denial passed: {result['freecad']}; "
                f"Qt {result['qt']}"
            )
            if args.preferences:
                print("FreeCAD preferences and timed-bypass dialog passed")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
