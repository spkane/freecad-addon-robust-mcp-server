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
    result = subprocess.run(
        [sys.executable, "-m", "freecad_mcp.server", "--pair-bridge"],
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
            # Delete only the credential created by this test; never remove a
            # replacement that another process may have installed meanwhile.
            from freecad_mcp.bridge import windows_credential_store

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
    """Initialize and perform a real FreeCAD tool call through an MCP client."""
    result = await session.initialize()
    assert result.server_info.name == "freecad-mcp"
    tools = await session.list_tools()
    assert any(tool.name == "get_freecad_version" for tool in tools.tools)
    call = await session.call_tool("get_freecad_version")
    assert not call.is_error


async def _check_harnesses(env: dict[str, str], port: int, mode: str) -> None:
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
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "freecad_mcp.server"], env=settings
    )
    with tempfile.TemporaryFile(mode="w+") as stderr:
        async with stdio_client(params, errlog=stderr) as streams:
            async with ClientSession(*streams) as session:
                await _check_harness_session(session)

    generator = await asyncio.create_subprocess_exec(
        sys.executable,
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
        sys.executable,
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
                except httpx2.ConnectError:
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
        await asyncio.wait_for(server.wait(), timeout=10)


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
    env = {
        **os.environ,
        "FREECAD_MCP_TESTING": "1",
        "FREECAD_AUTH_TEST_READY": str(ready),
        "HOME": str(tmp_path),
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
