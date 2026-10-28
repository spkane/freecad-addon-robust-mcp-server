"""Per-user bridge credential storage.

The workbench contains an identical copy because it runs in FreeCAD's separate
Python environment. Windows uses its native Credential Manager.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import stat
from pathlib import Path

_DIR = ".freecad-robust-mcp"
_FILE = "bridge-credential.json"


def _open_store(create: bool) -> int:
    """Open a private, user-owned credential directory without following links."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError(
            "Secure bridge credential storage is unavailable on this platform"
        )
    directory = Path.home() / _DIR
    if create:
        with contextlib.suppress(FileExistsError):
            directory.mkdir(mode=0o700)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        os.close(fd)
        raise RuntimeError("Bridge credential directory must be private and user-owned")
    return fd


def read_credential() -> tuple[str, str]:
    """Read the client ID and hex secret from a private credential file."""
    if os.name == "nt":
        if __package__:
            from .windows_credential_store import read_credential as read_windows
        else:
            from windows_credential_store import read_credential as read_windows  # type: ignore[import-not-found,no-redef]

        return read_windows()
    directory_fd = _open_store(False)
    try:
        fd = os.open(
            _FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd
        )
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
                or info.st_size > 1024
            ):
                raise RuntimeError(
                    "Bridge credential file must be private and user-owned"
                )
            with os.fdopen(fd, "rb", closefd=False) as file:
                payload = file.read(1025)
            if len(payload) > 1024:
                raise ValueError("Invalid bridge credential file")
            data = json.loads(payload)
            if not isinstance(data, dict) or set(data) != {"client_id", "secret"}:
                raise ValueError("Invalid bridge credential file")
            client_id, secret = data["client_id"], data["secret"]
            if not isinstance(client_id, str) or not isinstance(secret, str):
                raise ValueError("Invalid bridge credential file")
            return client_id, secret
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)


def create_credential() -> str:
    """Create one random credential without overwriting an existing pairing.

    Returns:
        The non-secret client ID of the new pairing.
    """
    if os.name == "nt":
        if __package__:
            from .windows_credential_store import create_credential as create_windows
        else:
            from windows_credential_store import create_credential as create_windows  # type: ignore[import-not-found,no-redef]

        return create_windows()
    directory_fd = _open_store(True)
    try:
        client_id = secrets.token_hex(16)
        secret = secrets.token_hex(32)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        fd = os.open(_FILE, flags, 0o600, dir_fd=directory_fd)
        try:
            payload = json.dumps({"client_id": client_id, "secret": secret}).encode()
            with os.fdopen(fd, "wb", closefd=False) as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            os.unlink(_FILE, dir_fd=directory_fd)
            raise
        finally:
            os.close(fd)
        return client_id
    finally:
        os.close(directory_fd)
