"""Classify FreeCAD startup conservatively before enabling the bridge."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# FreeCAD options that take a value without themselves executing a batch.
_VALUE_OPTIONS = frozenset(
    {
        "-u",
        "--user-cfg",
        "-s",
        "--system-cfg",
        "-M",
        "--module-path",
        "-E",
        "--macro-path",
        "-P",
        "--python-path",
        "--disable-addon",
        "--log-file",
    }
)
# Options that run a command or terminate without an interactive session.
_BATCH_OPTIONS = frozenset(
    {
        "-t",
        "--run-test",
        "-r",
        "--run-open",
        "-v",
        "--version",
        "--verbose",
        "-h",
        "--help",
        "--dump-config",
        "--get-config",
        "--set-config",
        "--pass",
        "--response-file",
    }
)
_FLAG_OPTIONS = frozenset(
    {
        "-c",
        "--console",
        "-l",
        "--write-log",
        "--keep-deprecated-paths",
        "--single-instance",
        "--safe-mode",
    }
)


def is_console_executable(executable: str) -> bool:
    """Identify FreeCAD's console executable without accepting partial names."""
    return Path(executable).name.lower() in {"freecadcmd", "freecadcmd.exe"}


def is_batch_invocation(arguments: Sequence[str]) -> bool:
    """Fail closed for scripts, batch options and unknown command-line options.

    Args:
        arguments: FreeCAD arguments excluding the executable.

    Returns:
        True if this invocation should not auto-start a long-lived bridge.
    """
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            return index + 1 < len(arguments)
        option = argument.split("=", 1)[0]
        if option in _BATCH_OPTIONS or any(
            argument.startswith(short) and argument != short for short in ("-t", "-r")
        ):
            return True
        if option in _VALUE_OPTIONS:
            if "=" not in argument:
                index += 1
                if index >= len(arguments):
                    return True
        elif any(
            argument.startswith(short) and argument != short
            for short in ("-u", "-s", "-M", "-E", "-P")
        ):
            pass
        elif argument not in _FLAG_OPTIONS:
            return True
        index += 1
    return False
