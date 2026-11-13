"""Capture the exact local macro bytes used for review and execution."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

MAX_MACRO_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class MacroSnapshot:
    """A resolved path, immutable bytes, and their SHA-256 digest."""

    path: str
    content: bytes
    sha256: str


def snapshot_macro(path: str) -> MacroSnapshot:
    """Read a bounded regular file once for subsequent review and execution.

    The returned immutable bytes must be displayed and executed directly; a
    caller must not reopen the path after a decision. The path is resolved for
    display and for distinguishing saved approvals of otherwise identical files.
    The caller is responsible for selecting an authorized macro location.

    Raises:
        OSError: If the path cannot be resolved or the file cannot be read.
        ValueError: If the file is not regular or exceeds the review size limit.
    """
    resolved = Path(path).resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(str(resolved), flags)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Macro must be a regular file")
        content = stream.read(MAX_MACRO_BYTES + 1)
    if len(content) > MAX_MACRO_BYTES:
        raise ValueError("Macro exceeds the review size limit")
    return MacroSnapshot(str(resolved), content, hashlib.sha256(content).hexdigest())


def resolve_macro(name: str, roots: tuple[str, ...]) -> MacroSnapshot:
    """Capture the first matching macro in the configured search directories.

    A macro name is a single filename without its .FCMacro extension. A missing
    user macro permits a system fallback; other read errors fail closed.
    """
    if (
        type(name) is not str
        or not name
        or name in {".", ".."}
        or any(char in name for char in "/\\:\0\r\n")
    ):
        raise ValueError("Macro name must be a single file name")
    for root in roots:
        candidate = str(Path(root) / (name + ".FCMacro"))
        try:
            return snapshot_macro(candidate)
        except FileNotFoundError:
            continue
    raise FileNotFoundError("Macro was not found")
