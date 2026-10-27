"""Tests for per-user bridge credential storage."""

import os
import stat
import sys
from pathlib import Path

import pytest

from freecad_mcp.bridge.authentication import credentials_from_config
from freecad_mcp.bridge.credential_store import create_credential, read_credential
from freecad_mcp.config import ServerConfig

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX credential store")


def test_pairing_is_private_and_does_not_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new credential is private, reusable, and protected from replacement."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    client_id = create_credential()
    loaded_id, secret = read_credential()
    assert loaded_id == client_id
    assert len(bytes.fromhex(secret)) == 32
    directory = tmp_path / ".freecad-robust-mcp"
    credential = directory / "bridge-credential.json"
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(credential.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        create_credential()
    assert read_credential() == (loaded_id, secret)


def test_insecure_credential_file_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A credential readable by another account is rejected."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    create_credential()
    path = tmp_path / ".freecad-robust-mcp" / "bridge-credential.json"
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="private and user-owned"):
        read_credential()


def test_symlink_credential_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The credential loader never follows a symlink."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    create_credential()
    path = tmp_path / ".freecad-robust-mcp" / "bridge-credential.json"
    path.unlink()
    path.symlink_to(tmp_path / "other")
    with pytest.raises(OSError):
        read_credential()


def test_mcp_server_loads_stored_pairing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The configured server loads the generated identity and can sign."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    client_id = create_credential()
    actual_id, sign = credentials_from_config(
        ServerConfig(bridge_client_id=None, bridge_secret=None)
    )
    assert actual_id == client_id
    assert len(sign(b"request")) == 32


def test_workbench_store_matches_server_store() -> None:
    """Both separately installed packages use the same storage implementation."""
    root = Path(__file__).resolve().parents[2]
    server = root / "src/freecad_mcp/bridge/credential_store.py"
    workbench = root / "freecad/RobustMCPBridge/freecad_mcp_bridge/credential_store.py"
    assert server.read_bytes() == workbench.read_bytes()


def test_pair_command_creates_reusable_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The pairing command creates the credential without printing its secret."""
    from freecad_mcp.server import main

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["freecad-mcp", "--pair-bridge"])
    main()
    client_id, secret = read_credential()
    output = capsys.readouterr().out
    assert client_id in output
    assert secret not in output
