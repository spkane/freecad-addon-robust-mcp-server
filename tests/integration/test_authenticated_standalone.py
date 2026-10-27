"""Real FreeCAD authenticated transport tests with test-only credentials."""

import asyncio
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from freecad_mcp.bridge.authentication import create_hmac_signer
from freecad_mcp.bridge.credential_store import create_credential, read_credential
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests" / "fixtures" / "freecad_authenticated_probe.py"


def _assert_truncated(*texts: str) -> None:
    """Check the bridge's byte limit and explicit truncation marker."""
    for text in texts:
        assert len(text.encode("utf-8")) <= 1_000_000
        assert text.endswith("\n[output truncated]\n")


@pytest.mark.standalone_freecad
@pytest.mark.asyncio
@pytest.mark.timeout(45)
async def test_authenticated_transports_with_real_freecad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A paired client executes CAD code; a different secret is rejected."""
    executable = os.environ.get("FREECAD_AUTH_TEST_COMMAND")
    if not executable:
        pytest.skip("Set FREECAD_AUTH_TEST_COMMAND")
    assert executable is not None
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    client_id = create_credential()
    _, secret_hex = read_credential()
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
        finally:
            if process.returncode is None:
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
