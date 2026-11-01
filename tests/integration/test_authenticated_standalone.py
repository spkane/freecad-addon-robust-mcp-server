"""Real FreeCAD authenticated transport tests with test-only credentials."""

import asyncio
import ctypes
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from ctypes import wintypes
from pathlib import Path

import httpx2
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from freecad_mcp.bridge.authentication import create_hmac_signer
from freecad_mcp.bridge.credential_store import read_credential
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests" / "fixtures" / "freecad_authenticated_probe.py"


def _server_python() -> str:
    """Use the installed wheel's interpreter in release verification jobs."""
    return os.environ.get("FREECAD_MCP_TEST_PYTHON", sys.executable)


@pytest.fixture
def isolated_pairing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[str, str]]:
    """Create a disposable pairing without replacing an existing credential."""
    executable = os.environ.get("FREECAD_AUTH_TEST_COMMAND")
    if not executable:
        if os.environ.get("FREECAD_AUTH_TEST_REQUIRED") == "1":
            pytest.fail("FREECAD_AUTH_TEST_COMMAND is required in this CI job")
        pytest.skip("Set FREECAD_AUTH_TEST_COMMAND")
    if os.name == "nt":
        if os.environ.get("FREECAD_AUTH_TEST_DISPOSABLE_WINDOWS") != "1":
            if os.environ.get("FREECAD_AUTH_TEST_REQUIRED") == "1":
                pytest.fail("Windows CI requires an explicitly disposable user account")
            pytest.skip("Windows requires an explicitly disposable user account")
        try:
            read_credential()
        except FileNotFoundError:
            pass
        else:
            pytest.fail("Refusing to replace an existing Windows bridge pairing")
    else:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

    pair_env = {**os.environ, "HOME": str(tmp_path)}
    result = subprocess.run(  # noqa: S603 - test interpreter selected by CI
        [_server_python(), "-m", "freecad_mcp.server", "--pair-bridge"],
        env=pair_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    client_id, secret_hex = read_credential()
    try:
        yield client_id, secret_hex
    finally:
        if os.name == "nt":
            # Pairing uses this lock too, so another pairing attempt cannot
            # replace the credential between the ownership check and deletion.
            from freecad_mcp.bridge import windows_credential_store

            with windows_credential_store._pairing_lock():
                if read_credential() == (client_id, secret_hex):
                    api = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined]
                    api.CredDeleteW.argtypes = [
                        wintypes.LPCWSTR,
                        wintypes.DWORD,
                        wintypes.DWORD,
                    ]
                    api.CredDeleteW.restype = wintypes.BOOL
                    if not api.CredDeleteW(windows_credential_store._TARGET, 1, 0):
                        raise OSError("Could not remove disposable Windows credential")


def _assert_truncated(*texts: str) -> None:
    """Check the bridge's byte limit and explicit truncation marker."""
    for text in texts:
        assert len(text.encode("utf-8")) <= 1_000_000
        assert text.endswith("\n[output truncated]\n")


async def _check_harness_session(session: ClientSession) -> None:
    """Exercise installed MCP tools, including the sketch regressions in #87."""
    result = await session.initialize()
    assert result.server_info.name == "freecad-mcp"
    tools = await session.list_tools()
    assert any(tool.name == "get_freecad_version" for tool in tools.tools)
    call = await session.call_tool("get_freecad_version")
    assert not call.is_error
    calls = (
        ("create_document", {"name": "ReleaseSketchRegression"}),
        (
            "create_partdesign_body",
            {"name": "Body", "doc_name": "ReleaseSketchRegression"},
        ),
        (
            "create_sketch",
            {
                "name": "BaseSketch",
                "body_name": "Body",
                "plane": "XY_Plane",
                "doc_name": "ReleaseSketchRegression",
            },
        ),
        (
            "add_sketch_rectangle",
            {
                "sketch_name": "BaseSketch",
                "x": -30,
                "y": -20,
                "width": 60,
                "height": 40,
                "doc_name": "ReleaseSketchRegression",
            },
        ),
        ("close_document", {"doc_name": "ReleaseSketchRegression"}),
    )
    for name, arguments in calls:
        tool_result = await session.call_tool(name, arguments=arguments)
        assert not tool_result.is_error, (name, tool_result)


async def _check_harnesses(
    env: dict[str, str], port: int, mode: str, *, use_default: bool = False
) -> None:
    """Exercise stdio and API-key HTTP clients against the paired bridge."""
    settings = {
        **env,
        "FREECAD_MODE": mode,
        "FREECAD_SOCKET_HOST": "127.0.0.1",
        "FREECAD_XMLRPC_PORT": str(port) if mode == "xmlrpc" else "9875",
        "FREECAD_SOCKET_PORT": str(port) if mode == "socket" else "9876",
        "FREECAD_TRANSPORT": "stdio",
    }
    settings.pop("FREECAD_HTTP_API_KEY", None)
    if use_default:
        assert mode == "xmlrpc"
        settings.pop("FREECAD_MODE", None)
    params = StdioServerParameters(
        command=_server_python(), args=["-m", "freecad_mcp.server"], env=settings
    )
    with tempfile.TemporaryFile(mode="w+") as stderr:
        async with stdio_client(params, errlog=stderr) as streams:
            async with ClientSession(*streams) as session:
                await _check_harness_session(session)

    generator = await asyncio.create_subprocess_exec(
        _server_python(),
        "-m",
        "freecad_mcp.server",
        "--generate-http-api-key",
        env=settings,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, _ = await generator.communicate()
    assert generator.returncode == 0
    key = output.decode("ascii").strip()
    assert len(key) >= 32
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        http_port = probe.getsockname()[1]
    settings.update(
        FREECAD_TRANSPORT="http",
        FREECAD_HTTP_HOST="127.0.0.1",
        FREECAD_HTTP_PORT=str(http_port),
        FREECAD_HTTP_API_KEY=key,
    )
    server = await asyncio.create_subprocess_exec(
        _server_python(),
        "-m",
        "freecad_mcp.server",
        env=settings,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with httpx2.AsyncClient(timeout=2) as http:
            url = f"http://127.0.0.1:{http_port}/mcp"
            for _ in range(100):
                if server.returncode is not None:
                    pytest.fail("MCP HTTP server exited before becoming ready")
                try:
                    response = await http.post(url)
                    break
                except (httpx2.ConnectError, httpx2.ConnectTimeout):
                    await asyncio.sleep(0.1)
            else:
                pytest.fail("MCP HTTP server did not become ready")
            assert response.status_code == 401
            http.headers["Authorization"] = "Bearer incorrect"
            assert (await http.post(url)).status_code == 401
            http.headers["Authorization"] = f"Bearer {key}"
            async with streamable_http_client(url, http_client=http) as streams:
                async with ClientSession(*streams[:2]) as session:
                    await _check_harness_session(session)
    finally:
        if server.returncode is None:
            server.terminate()
        try:
            await asyncio.wait_for(server.wait(), timeout=10)
        except TimeoutError:
            server.kill()
            await server.wait()


async def _check_unauthenticated_bridge_request(port: int, mode: str) -> None:
    """Confirm the real listener rejects a request without authentication."""
    if mode == "xmlrpc":
        async with httpx2.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/",
                content=b"<methodCall><methodName>ping</methodName></methodCall>",
                headers={"Content-Type": "text/xml"},
            )
            assert response.status_code == 401
    else:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            writer.write(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
            await writer.drain()
            response = json.loads(await asyncio.wait_for(reader.readline(), timeout=5))
            assert response.get("error") == "Bridge authentication required"
        finally:
            writer.close()
            await writer.wait_closed()


@pytest.mark.standalone_freecad
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_authenticated_transports_with_real_freecad(
    tmp_path: Path, isolated_pairing: tuple[str, str]
) -> None:
    """A paired client executes CAD code; a different secret is rejected."""
    executable = os.environ.get("FREECAD_AUTH_TEST_COMMAND")
    assert executable is not None
    client_id, secret_hex = isolated_pairing
    ready = tmp_path / "ports.json"
    log_path = tmp_path / "freecad.log"
    mod_dir = tmp_path / "Mod"
    installer = await asyncio.create_subprocess_exec(
        sys.executable,
        str(ROOT / "scripts/install_workbench.py"),
        "--mod-dir",
        str(mod_dir),
    )
    assert await installer.wait() == 0
    env = {
        **os.environ,
        "FREECAD_MCP_TESTING": "1",
        "FREECAD_AUTH_TEST_READY": str(ready),
        "HOME": str(tmp_path),
        "FREECAD_AUTH_TEST_WORKBENCH_PATH": str(
            mod_dir / "RobustMCPBridge" / "freecad" / "RobustMCPBridge"
        ),
    }
    env.pop("FREECAD_BRIDGE_CLIENT_ID", None)
    env.pop("FREECAD_BRIDGE_SECRET", None)
    with log_path.open("w+", encoding="utf-8") as log:
        process = await asyncio.create_subprocess_exec(
            executable, str(PROBE), stdout=log, stderr=subprocess.STDOUT, env=env
        )
        try:
            deadline = time.monotonic() + 20
            while not ready.exists() and time.monotonic() < deadline:
                if process.returncode is not None:
                    break
                await asyncio.sleep(0.05)
            if not ready.exists():
                log.flush()
                pytest.fail(f"FreeCAD bridge did not start: {log_path.read_text()}")
            ports = json.loads(ready.read_text(encoding="utf-8"))
            for mode, bridge_type in (
                ("xmlrpc", XmlRpcBridge),
                ("socket", SocketBridge),
            ):
                await _check_unauthenticated_bridge_request(ports[mode], mode)
                wrong = bridge_type(
                    host="127.0.0.1",
                    port=ports[mode],
                    client_id=client_id,
                    signer=create_hmac_signer(b"\x02" * 32),
                )
                try:
                    with pytest.raises(ConnectionError):
                        await wrong.connect()
                finally:
                    await wrong.disconnect()
                bridge = bridge_type(
                    host="127.0.0.1",
                    port=ports[mode],
                    client_id=client_id,
                    signer=create_hmac_signer(bytes.fromhex(secret_hex)),
                )
                try:
                    await bridge.connect()
                    result = await bridge.execute_python(
                        "import Part\n_result_ = Part.makeBox(2, 3, 4).Volume"
                    )
                    assert result.success
                    assert result.result == pytest.approx(24.0)
                    output = await bridge.execute_python("print('x' * 100000, end='')")
                    assert output.success
                    assert len(output.stdout) == 100000
                    output = await bridge.execute_python(
                        "print('left\\x00right', end='')"
                    )
                    assert output.success
                    assert output.stdout == r"left\x00right"
                    output = await bridge.execute_python(
                        "import sys\nprint('é' * 600000)\n"
                        "print('x' * 1100000, file=sys.stderr)"
                    )
                    assert output.success
                    _assert_truncated(output.stdout, output.stderr)
                    error = await bridge.execute_python(
                        "raise ValueError('é' * 600000)"
                    )
                    assert not error.success
                    assert error.error_type == "ValueError"
                    assert error.error_traceback is not None
                    _assert_truncated(error.stderr, error.error_traceback)
                    oversized = await bridge.execute_python("_result_ = 'x' * 1000001")
                    assert not oversized.success
                    assert oversized.error_type == "ResultValidationError"
                    assert "FreeCAD changes may have occurred" in oversized.stderr
                    interrupted = await bridge.execute_python(
                        "raise SystemExit('test')"
                    )
                    assert not interrupted.success
                    assert interrupted.error_type == "SystemExit"
                    after = await bridge.execute_python("_result_ = 42")
                    assert after.success and after.result == 42
                finally:
                    await bridge.disconnect()
                await _check_harnesses(env, ports[mode], mode)
            await _check_harnesses(env, ports["xmlrpc"], "xmlrpc", use_default=True)
        finally:
            if process.returncode is None:
                if os.name == "nt":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGINT)
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except TimeoutError:
                        process.kill()
                        await process.wait()


@pytest.mark.standalone_freecad
@pytest.mark.timeout(90)
@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", ["socket", "xmlrpc"])
async def test_real_freecad_port_conflict_preserves_other_transport(
    tmp_path: Path, isolated_pairing: tuple[str, str], blocked: str
) -> None:
    """Real FreeCAD reports the occupied listener and authenticates the other."""
    executable = os.environ["FREECAD_AUTH_TEST_COMMAND"]
    client_id, secret_hex = isolated_pairing
    ready = tmp_path / "partial-ports.json"
    log_path = tmp_path / "partial-freecad.log"
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "FREECAD_AUTH_TEST_READY": str(ready),
        "FREECAD_AUTH_TEST_ALLOW_PARTIAL": "1",
    }
    env.pop("FREECAD_BRIDGE_CLIENT_ID", None)
    env.pop("FREECAD_BRIDGE_SECRET", None)
    with socket.socket() as blocker, log_path.open("w+", encoding="utf-8") as log:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        port = blocker.getsockname()[1]
        env[f"FREECAD_AUTH_TEST_{blocked.upper()}_PORT"] = str(port)
        process = await asyncio.create_subprocess_exec(
            executable, str(PROBE), stdout=log, stderr=subprocess.STDOUT, env=env
        )
        try:
            deadline = time.monotonic() + 30
            while not ready.exists() and time.monotonic() < deadline:
                if process.returncode is not None:
                    break
                await asyncio.sleep(0.05)
            if not ready.exists():
                log.flush()
                pytest.fail(f"FreeCAD bridge did not start: {log_path.read_text()}")
            data = json.loads(ready.read_text(encoding="utf-8"))
            active = "xmlrpc" if blocked == "socket" else "socket"
            assert data["status"]["listeners"][blocked] == "failed"
            assert data["status"]["listeners"][active] == "running"
            message = data["status"]["listener_errors"][blocked]
            assert str(port) in message and "in use" in message
            assert "preferences" in message and "client configuration" in message
            await _check_unauthenticated_bridge_request(data[active], active)
            bridge_class = SocketBridge if active == "socket" else XmlRpcBridge
            bridge = bridge_class(
                host="127.0.0.1",
                port=data[active],
                client_id=client_id,
                signer=create_hmac_signer(bytes.fromhex(secret_hex)),
            )
            try:
                await bridge.connect()
                result = await bridge.execute_python("_result_ = 42")
                assert result.success and result.result == 42
            finally:
                await bridge.disconnect()
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    process.kill()
                    await process.wait()


@pytest.mark.standalone_freecad
@pytest.mark.timeout(120)
@pytest.mark.usefixtures("isolated_pairing")
@pytest.mark.parametrize("early", [False, True], ids=["script", "workbench-init"])
@pytest.mark.parametrize(
    ("interactive", "headless_enabled", "batch_enabled", "expected"),
    [
        (True, True, False, True),
        (True, False, True, False),
        (False, True, False, False),
        (False, True, True, True),
    ],
)
def test_headless_workbench_autostart(
    tmp_path: Path,
    early: bool,
    interactive: bool,
    headless_enabled: bool,
    batch_enabled: bool,
    expected: bool,
) -> None:
    """Exercise real console startup, batch gating, and clean shutdown."""
    executable = os.environ["FREECAD_AUTH_TEST_COMMAND"]
    probe = ROOT / "tests" / "fixtures" / "freecad_autostart_probe.py"
    ready = tmp_path / "autostart-result.json"
    ports = []
    for _ in range(2):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "MCP_TEST_HEADLESS": "1" if headless_enabled else "0",
        "MCP_TEST_BATCH": "1" if batch_enabled else "0",
        "MCP_TEST_XMLRPC_PORT": str(ports[0]),
        "MCP_TEST_SOCKET_PORT": str(ports[1]),
        "MCP_TEST_RESULT": str(ready),
    }
    env.pop("FREECAD_MCP_TESTING", None)
    command = [
        executable,
        "--user-cfg",
        str(tmp_path / "user.cfg"),
        "--system-cfg",
        str(tmp_path / "system.cfg"),
    ]
    if early:
        # FreeCAD imports namespace workbenches before running the script or
        # accepting console input. Exercise the initializer in that early phase.
        module_dir = tmp_path / "modules"
        workbench = module_dir / "freecad" / "MCPStartupProbe"
        workbench.mkdir(parents=True)
        (workbench / "__init__.py").write_text(
            "import os, runpy\n"
            "os.environ.pop('FREECAD_MCP_TESTING', None)\n"
            "try:\n"
            f"    runpy.run_path({str(probe)!r})\n"
            "finally:\n"
            "    os.environ['FREECAD_MCP_TESTING'] = '1'\n",
            encoding="utf-8",
        )
        env["FREECAD_MCP_TESTING"] = "1"
        command.extend(["--module-path", str(module_dir)])
        batch_script = tmp_path / "batch.py"
        batch_script.write_text("pass\n", encoding="utf-8")
        if interactive:
            source = "pass\n"
        else:
            command.append(str(batch_script))
            source = None
    elif interactive:
        source = f"import runpy; _ = runpy.run_path({str(probe)!r})\n"
    else:
        command.append(str(probe))
        source = None
    result = subprocess.run(  # noqa: S603 - explicit test executable
        command,
        input=source,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert ready.exists(), result.stdout + result.stderr
    assert json.loads(ready.read_text(encoding="utf-8")) == {
        "started": expected,
        "listening": expected,
    }, result.stdout + result.stderr
