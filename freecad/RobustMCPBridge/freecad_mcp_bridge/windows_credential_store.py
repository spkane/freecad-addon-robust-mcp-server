"""Per-user bridge credential storage using Windows Credential Manager."""

from __future__ import annotations

import ctypes
import json
import secrets
from contextlib import contextmanager
from ctypes import wintypes
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

_TARGET = "FreeCADRobustMCPBridge:default"
_GENERIC = 1
_LOCAL_MACHINE = 2
_NOT_FOUND = 1168


@contextmanager
def _pairing_lock() -> Iterator[None]:
    """Serialize pairing attempts across Windows sessions on this machine."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.ReleaseMutex.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateMutexW(None, False, "Global\\FreeCADRobustMCPBridgePairing")
    if not handle:
        raise OSError(ctypes.get_last_error(), "Cannot create bridge pairing lock")  # type: ignore[attr-defined]
    acquired = False
    try:
        result = kernel.WaitForSingleObject(handle, 10000)
        if result not in (0, 0x80):
            raise RuntimeError("Cannot acquire bridge pairing lock")
        acquired = True
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _api() -> Any:
    """Load typed Credential Manager functions."""
    api = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined]
    api.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_Credential)),
    ]
    api.CredReadW.restype = wintypes.BOOL
    api.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    return api


def read_credential() -> tuple[str, str]:
    """Read the current user's locally persisted bridge credential."""
    api = _api()
    credential = ctypes.POINTER(_Credential)()
    if not api.CredReadW(_TARGET, _GENERIC, 0, ctypes.byref(credential)):
        code = ctypes.get_last_error()  # type: ignore[attr-defined]
        if code == _NOT_FOUND:
            raise FileNotFoundError("Bridge pairing does not exist")
        raise OSError(code, "Cannot read bridge pairing from Credential Manager")
    try:
        value = credential.contents
        if value.CredentialBlobSize > 1024:
            raise ValueError("Invalid bridge credential")
        payload = ctypes.string_at(value.CredentialBlob, value.CredentialBlobSize)
        data = json.loads(payload)
        if (
            not isinstance(data, dict)
            or set(data) != {"client_id", "secret"}
            or not isinstance(data["client_id"], str)
            or not isinstance(data["secret"], str)
        ):
            raise ValueError("Invalid bridge credential")
        return data["client_id"], data["secret"]
    finally:
        api.CredFree(credential)


def create_credential() -> str:
    """Create a locally persisted random credential for the current user.

    Returns:
        The non-secret client ID.
    """
    with _pairing_lock():
        return _create_locked()


def _create_locked() -> str:
    """Create a credential while holding the pairing lock."""
    try:
        read_credential()
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError("Bridge pairing already exists")
    client_id = secrets.token_hex(16)
    payload = json.dumps(
        {"client_id": client_id, "secret": secrets.token_hex(32)}
    ).encode()
    blob = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
    credential = _Credential()
    credential.Type = _GENERIC
    credential.TargetName = _TARGET
    credential.CredentialBlobSize = len(payload)
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = _LOCAL_MACHINE
    if not _api().CredWriteW(ctypes.byref(credential), 0):
        raise OSError(ctypes.get_last_error(), "Cannot save bridge pairing")  # type: ignore[attr-defined]
    return client_id
