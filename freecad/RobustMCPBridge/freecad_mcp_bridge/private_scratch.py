"""Create short-lived user-private directories for agent-facing artifacts.

This module is mirrored in the MCP server package so that its source can be
included in generated code for FreeCAD instances without this workbench.
"""

import contextlib
import ctypes
import os
import secrets
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path


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
            yield path
        return
    path = _windows_private_directory(parent, prefix)
    try:
        yield path
    finally:
        shutil.rmtree(path)
