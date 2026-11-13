"""Local, exact-content approvals for macros.

The store is local policy, not a remote authorization interface. Callers must
only add entries following an explicit user decision. A matching digest does
not guarantee the safety of imports, arguments, or other files used by a macro.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ENTRIES = 1024
_PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/RobustMCPBridge"
_PARAM_KEY = "ApprovedMacroVersions"


@dataclass(frozen=True, slots=True)
class MacroApproval:
    """A canonical macro path and the SHA-256 of its approved bytes."""

    path: str
    sha256: str

    def __post_init__(self) -> None:
        """Reject malformed records instead of broadening approval scope."""
        if type(self.path) is not str or not Path(self.path).is_absolute():
            raise ValueError("Macro approval path must be absolute")
        if "\x00" in self.path or len(self.path) > 4096:
            raise ValueError("Invalid macro approval path")
        if type(self.sha256) is not str or not _DIGEST.fullmatch(self.sha256):
            raise ValueError("Invalid macro approval SHA-256")


class MacroApprovalStore:
    """Serialize updates to the persisted local approval list.

    Read and write callbacks are supplied by the host, allowing the store to
    use FreeCAD preferences without exposing those preferences to clients.
    Malformed or unavailable persisted data raises instead of granting access.
    """

    def __init__(self, read: Callable[[], str], write: Callable[[str], None]) -> None:
        """Create a store using host-controlled persistence callbacks."""
        self._read = read
        self._write = write
        self._lock = threading.RLock()

    def _load(self) -> list[MacroApproval]:
        raw = self._read()
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if (
                type(data) is not dict
                or set(data) != {"version", "approvals"}
                or data["version"] != 1
                or type(data["version"]) is not int
                or type(data["approvals"]) is not list
                or len(data["approvals"]) > _MAX_ENTRIES
            ):
                raise ValueError("Invalid macro approval list")
            entries = []
            for item in data["approvals"]:
                if type(item) is not dict or set(item) != {"path", "sha256"}:
                    raise ValueError("Invalid macro approval entry")
                entries.append(MacroApproval(item["path"], item["sha256"]))
            if len(entries) != len(set(entries)):
                raise ValueError("Duplicate macro approval")
            return entries
        except (TypeError, KeyError, json.JSONDecodeError) as error:
            raise ValueError("Invalid macro approval list") from error

    def entries(self) -> tuple[MacroApproval, ...]:
        """Return a stable snapshot of the locally saved approvals."""
        with self._lock:
            return tuple(self._load())

    def contains(self, approval: MacroApproval) -> bool:
        """Check an exact path and content digest, never a filename alone."""
        with self._lock:
            return approval in self._load()

    def add(self, approval: MacroApproval) -> None:
        """Persist one explicit local approval without duplicating entries."""
        if type(approval) is not MacroApproval:
            raise TypeError("Expected a validated macro approval")
        with self._lock:
            entries = self._load()
            if approval in entries:
                return
            if len(entries) >= _MAX_ENTRIES:
                raise ValueError("Macro approval list is full")
            entries.append(approval)
            self._save(entries)

    def remove(self, approval: MacroApproval) -> bool:
        """Remove an exact entry and return whether it existed."""
        with self._lock:
            entries = self._load()
            if approval not in entries:
                return False
            entries.remove(approval)
            self._save(entries)
            return True

    def clear(self) -> None:
        """Remove every saved approval, including malformed saved state."""
        with self._lock:
            self._save([])

    def _save(self, entries: list[MacroApproval]) -> None:
        self._write(
            json.dumps(
                {
                    "version": 1,
                    "approvals": [
                        {"path": item.path, "sha256": item.sha256} for item in entries
                    ],
                },
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )


def freecad_approval_store() -> MacroApprovalStore:
    """Use FreeCAD's local user preferences for macro approval persistence.

    The GUI owns all calls to this store. It must not be exposed to an MCP
    client as a method for modifying the saved list.
    """
    import FreeCAD

    params = FreeCAD.ParamGet(_PARAM_PATH)
    return MacroApprovalStore(
        lambda: params.GetString(_PARAM_KEY, ""),
        lambda value: params.SetString(_PARAM_KEY, value),
    )
