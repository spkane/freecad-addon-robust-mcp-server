"""Windows Credential Manager integration for bridge pairing."""

import ctypes
import os
import uuid
from ctypes import wintypes

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Credential Manager")


def test_windows_credential_round_trip_and_no_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use a temporary Credential Manager target and remove it after the test."""
    from freecad_mcp.bridge import windows_credential_store as store

    target = f"FreeCADRobustMCPBridge:test:{uuid.uuid4()}"
    monkeypatch.setattr(store, "_TARGET", target)
    api = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined]
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    try:
        client_id = store.create_credential()
        actual_id, secret = store.read_credential()
        assert actual_id == client_id
        assert len(bytes.fromhex(secret)) == 32
        with pytest.raises(FileExistsError):
            store.create_credential()
        assert store.read_credential() == (actual_id, secret)
    finally:
        api.CredDeleteW(target, 1, 0)
