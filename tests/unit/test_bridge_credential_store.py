"""Tests for per-user bridge credential storage."""

import os
import stat
from pathlib import Path

import pytest

from freecad_mcp.bridge.credential_store import create_credential, read_credential

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
