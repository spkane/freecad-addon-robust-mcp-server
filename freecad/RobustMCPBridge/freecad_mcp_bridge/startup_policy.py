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
# These batch options also consume one argument. Do not interpret that value
# as an explicit console flag when establishing the execution safety boundary.
_BATCH_VALUE_OPTIONS = frozenset(
    {
        "-t",
        "--run-test",
        "-r",
        "--run-open",
        "--get-config",
        "--set-config",
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


def is_console_invocation(executable: str, arguments: Sequence[str]) -> bool:
    """Identify the console binary or FreeCAD's explicit console mode.

    A Qt GUI application, if present, must still take precedence over this
    command-line signal when choosing the execution thread.
    """
    if is_console_executable(executable):
        return True
    if Path(executable).name.lower() not in {"freecad", "freecad.exe"}:
        return False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in {"--", "--pass"}:
            return False
        if argument in {"-c", "--console"}:
            return True
        option = argument.split("=", 1)[0]
        if option in _VALUE_OPTIONS or option in _BATCH_VALUE_OPTIONS:
            if "=" not in argument:
                index += 1
                if index >= len(arguments):
                    break
        elif (
            argument in _FLAG_OPTIONS
            or argument in _BATCH_OPTIONS
            or any(
                argument.startswith(short) and argument != short
                for short in ("-u", "-s", "-M", "-E", "-P", "-t", "-r")
            )
        ):
            pass
        else:
            # Unknown options or positional arguments make later tokens
            # ambiguous; never infer headless mode from those tokens.
            break
        index += 1
    return False


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
                if index >= len(arguments) or arguments[index].startswith("-"):
                    # Missing or option-like values are ambiguous. Do not
                    # start an interactive bridge for a malformed command.
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
