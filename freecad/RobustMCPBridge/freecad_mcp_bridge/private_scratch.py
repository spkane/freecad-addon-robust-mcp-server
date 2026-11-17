"""Create short-lived user-private directories for agent-facing artifacts.

This module is mirrored in the MCP server package so that its source can be
included in generated code for FreeCAD instances without this workbench.
"""

import contextlib
import ctypes
import errno
import os
import secrets
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path


def _darwin_verify_empty_acl(libc: ctypes.CDLL, fd: int) -> None:
    """Accept a missing or valid empty ACL and reject entries or errors."""
    ctypes.set_errno(0)
    remaining = libc.acl_get_fd_np(fd, 0x100)
    if remaining:
        try:
            if libc.acl_valid(remaining) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            entry = ctypes.c_void_p()
            ctypes.set_errno(0)
            result = libc.acl_get_entry(remaining, 0, ctypes.byref(entry))
            if result == 0:
                raise OSError("Scratch directory still has an access control list")
            error = ctypes.get_errno()
            # Darwin returns EINVAL for ACL_FIRST_ENTRY on a valid empty ACL.
            if result != -1 or error != errno.EINVAL:
                raise OSError(error, os.strerror(error))
        finally:
            libc.acl_free(remaining)
    elif ctypes.get_errno() != errno.ENOENT:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _darwin_clear_inherited_acl(path: str) -> None:
    """Remove inherited macOS ACL entries before placing artifacts in a directory."""
    libc = ctypes.CDLL(None, use_errno=True)
    acl_init = libc.acl_init
    acl_init.argtypes = [ctypes.c_int]
    acl_init.restype = ctypes.c_void_p
    acl_set = libc.acl_set_fd_np
    acl_set.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    acl_set.restype = ctypes.c_int
    acl_get = libc.acl_get_fd_np
    acl_get.argtypes = [ctypes.c_int, ctypes.c_int]
    acl_get.restype = ctypes.c_void_p
    acl_valid = libc.acl_valid
    acl_valid.argtypes = [ctypes.c_void_p]
    acl_valid.restype = ctypes.c_int
    acl_get_entry = libc.acl_get_entry
    acl_get_entry.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    acl_get_entry.restype = ctypes.c_int
    acl_free = libc.acl_free
    acl_free.argtypes = [ctypes.c_void_p]
    acl_free.restype = ctypes.c_int
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
    try:
        info = os.fstat(fd)
        current = os.lstat(path)
        if (
            not stat.S_ISDIR(info.st_mode)
            or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise OSError("Scratch directory identity or permissions changed")
        acl = acl_init(1)
        if not acl:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        try:
            if acl_set(fd, acl, 0x100) != 0:  # ACL_TYPE_EXTENDED
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
        finally:
            acl_free(acl)
        _darwin_verify_empty_acl(libc, fd)
        verified = os.fstat(fd)
        current = os.lstat(path)
        if (
            (verified.st_dev, verified.st_ino) != (current.st_dev, current.st_ino)
            or verified.st_uid != os.getuid()
            or stat.S_IMODE(verified.st_mode) != 0o700
        ):
            raise OSError("Scratch directory identity or permissions changed")
        if os.listdir(fd):  # noqa: PTH208 - inspect the opened directory, not a pathname
            raise OSError("Scratch directory was modified before it became private")
    finally:
        os.close(fd)


def _windows_private_directory(parent: str, prefix: str) -> str:
    """Atomically create a directory with a protected Windows DACL.

    Python before 3.11.10 ignores the mode argument on Windows. Apply the
    same protected DACL used by modern CPython for mode 0700 explicitly so
    FreeCAD's bundled interpreter does not inherit a permissive parent ACL.
    """
    from ctypes import wintypes

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.DWORD),
            ("security_descriptor", ctypes.c_void_p),
            ("inherit_handle", wintypes.BOOL),
        ]

    win_dll = vars(ctypes)["WinDLL"]
    get_error = vars(ctypes)["get_last_error"]
    win_error = vars(ctypes)["WinError"]
    advapi = win_dll("advapi32", use_last_error=True)
    kernel = win_dll("kernel32", use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
    ]
    convert.restype = wintypes.BOOL
    create = kernel.CreateDirectoryW
    create.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(SecurityAttributes)]
    create.restype = wintypes.BOOL
    volume_path = kernel.GetVolumePathNameW
    volume_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    volume_path.restype = wintypes.BOOL
    volume_info = kernel.GetVolumeInformationW
    volume_info.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    volume_info.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    volume = ctypes.create_unicode_buffer(32768)
    flags = wintypes.DWORD()
    if not volume_path(parent, volume, len(volume)):
        raise win_error(get_error())
    if not volume_info(volume, None, 0, None, None, ctypes.byref(flags), None, 0):
        raise win_error(get_error())
    if not flags.value & 0x00000008:  # FILE_PERSISTENT_ACLS
        raise OSError("User home filesystem does not support persistent ACLs")
    descriptor = ctypes.c_void_p()
    if not convert(
        "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)",
        1,
        ctypes.byref(descriptor),
        None,
    ):
        raise win_error(get_error())
    try:
        attributes = SecurityAttributes(
            ctypes.sizeof(SecurityAttributes), descriptor, False
        )
        for _ in range(100):
            path = str(Path(parent) / (prefix + secrets.token_hex(16)))
            if create(path, ctypes.byref(attributes)):
                return path
            error = get_error()
            if error != 183:  # ERROR_ALREADY_EXISTS
                raise win_error(error)
        raise FileExistsError("Unable to create a unique private scratch directory")
    finally:
        kernel.LocalFree(descriptor)


@contextlib.contextmanager
def private_scratch_directory(prefix: str) -> Iterator[str]:
    """Create private scratch space under the current user's home and remove it.

    Access by the same user, system administrators, and backups is not blocked.
    If the home directory cannot be used, creation fails rather than falling
    back to a potentially shared temporary location.
    """
    if not prefix or Path(prefix).name != prefix or prefix in {".", ".."}:
        raise ValueError("Scratch prefix must be a single path component")
    parent_path = Path.home()
    if not parent_path.is_absolute():
        raise OSError("Cannot determine an absolute user home directory")
    parent = str(parent_path)
    if os.name != "nt":
        with tempfile.TemporaryDirectory(prefix=prefix, dir=parent) as path:
            if sys.platform == "darwin":
                _darwin_clear_inherited_acl(path)
            yield path
        return
    path = _windows_private_directory(parent, prefix)
    try:
        yield path
    finally:
        shutil.rmtree(path)
