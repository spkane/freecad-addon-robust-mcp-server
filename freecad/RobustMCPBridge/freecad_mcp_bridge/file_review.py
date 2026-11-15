"""Snapshot filesystem targets for FreeCAD-owned file-operation review.

Path-based FreeCAD APIs may reopen a file after validation. Revalidation
therefore detects changes before dispatch but is not an atomic filesystem
sandbox; a process that can modify the target can still race the operation.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

FileAction = Literal["read", "write", "delete"]


@dataclass(frozen=True, slots=True)
class FileIdentity:
    """Stable identity and selected change indicators for a filesystem entry."""

    device: int
    inode: int
    mode: int
    owner: int
    group: int
    link_count: int
    size: int
    modified_ns: int
    changed_ns: int


def _identity(value: os.stat_result) -> FileIdentity:
    return FileIdentity(
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


@dataclass(frozen=True, slots=True)
class FileReviewSnapshot:
    """An operation and the target the local user is asked to review."""

    action: FileAction
    requested_path: str
    absolute_path: str
    resolved_path: str
    existing_parent: str
    parent_device: int
    parent_inode: int
    parent_mode: int
    parent_owner: int
    parent_group: int
    leaf: FileIdentity | None
    target: FileIdentity | None
    preceding_paths: tuple[str, ...] = field(default=(), compare=False)

    @property
    def exists(self) -> bool:
        """Whether the final path entry exists, including a dangling symlink."""
        return self.leaf is not None

    @property
    def is_symlink(self) -> bool:
        """Return whether the final path component is a symbolic link."""
        return self.leaf is not None and stat.S_ISLNK(self.leaf.mode)

    def unchanged(self) -> bool:
        """Check whether the path still names the same snapshot before dispatch."""
        try:
            return not any(os.path.lexists(path) for path in self.preceding_paths) and (
                snapshot_file(self.requested_path, self.action) == self
            )
        except (OSError, ValueError):
            return False


def snapshot_file(path: str, action: str) -> FileReviewSnapshot:
    """Resolve a file target and record its identity for local review.

    Relative paths are anchored to the current process working directory
    without removing ``..`` before resolving symbolic links. Existing targets
    must be regular files; a write may also target an absent file beneath an
    existing ancestor. Dangling final-component symlinks fail closed.

    Raises:
        ValueError: For unsupported actions, paths, or file types.
        OSError: If the target cannot be resolved or inspected.
    """
    if type(path) is not str or not path or any(c in path for c in "\x00\r\n\t"):
        raise ValueError("A nonempty file path is required")
    if action not in ("read", "write", "delete"):
        raise ValueError("Unsupported file operation")
    absolute = path if Path(path).is_absolute() else str(Path.cwd() / path)
    if not Path(absolute).is_absolute():
        raise ValueError("File target must resolve to an absolute path")
    resolved = os.path.realpath(absolute)
    parent_path = Path(resolved).parent
    while True:
        try:
            parent = parent_path.stat()
            break
        except FileNotFoundError:
            if action != "write" or parent_path == parent_path.parent:
                raise
            parent_path = parent_path.parent
    if not stat.S_ISDIR(parent.st_mode):
        raise ValueError("File target parent must be a directory")
    try:
        leaf_stat = os.lstat(absolute)
    except FileNotFoundError:
        if action != "write":
            raise
        leaf_stat = None
        target_stat = None
    else:
        target_stat = Path(absolute).stat()
        if not stat.S_ISREG(target_stat.st_mode):
            raise ValueError("File target must be a regular file")
    return FileReviewSnapshot(
        action=cast("FileAction", action),
        requested_path=path,
        absolute_path=absolute,
        resolved_path=resolved,
        existing_parent=str(parent_path),
        parent_device=parent.st_dev,
        parent_inode=parent.st_ino,
        parent_mode=parent.st_mode,
        parent_owner=parent.st_uid,
        parent_group=parent.st_gid,
        leaf=_identity(leaf_stat) if leaf_stat is not None else None,
        target=_identity(target_stat) if target_stat is not None else None,
    )
