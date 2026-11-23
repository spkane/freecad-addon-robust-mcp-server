"""Bind a reviewed operation to one live FreeCAD document instance."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class _Reservation:
    """Track a document before and after a review accepts it."""

    name: str
    document: Any
    expiry: float
    owner: str | None
    admitted: bool = False


class DocumentReservations:
    """Keep bounded, short-lived strong references until a review takes them.

    Capture and claim run on the FreeCAD GUI thread. The socket listener can
    transfer or discard a capture without resolving the live document. The
    single-use token binds the document to the review, and a retained wrapper
    prevents Python identity reuse after closure.
    """

    def __init__(self, capacity: int, lifetime: float = 300.0) -> None:
        """Initialize the reservation limit and lifetime in seconds."""
        if capacity < 1 or lifetime <= 0:
            raise ValueError("Invalid document reservation limits")
        self._capacity = capacity
        self._lifetime = lifetime
        self._entries: dict[str, _Reservation] = {}
        self._owners: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._closed = False

    def reserve(self, name: str, document: Any, owner: str | None = None) -> str:
        """Reserve the exact document selected on the GUI thread."""
        if not isinstance(name, str) or not name or document is None:
            raise ValueError("A named live document is required")
        with self._lock:
            if self._closed:
                raise RuntimeError("Document reservations are closed")
            if owner is not None and not self._owners.get(owner, False):
                raise RuntimeError("Document reservation session is closed")
            now = time.monotonic()
            for token, entry in list(self._entries.items()):
                if now >= entry.expiry:
                    del self._entries[token]
            if len(self._entries) >= self._capacity:
                raise RuntimeError("Document reservation capacity reached")
            token = secrets.token_urlsafe(32)
            self._entries[token] = _Reservation(
                name, document, now + self._lifetime, owner
            )
            return token

    def admit(self, token: str, name: str) -> None:
        """Transfer a live capture from its socket session to a queued review."""
        with self._lock:
            entry = self._entries.get(token)
            now = time.monotonic()
            if (
                self._closed
                or entry is None
                or entry.name != name
                or entry.admitted
                or now >= entry.expiry
            ):
                raise ValueError("Document reservation unavailable")
            entry.owner = None
            entry.admitted = True
            entry.expiry = now + self._lifetime

    def take(
        self, token: str, name: str, resolve: Callable[[str], Any]
    ) -> Callable[[], bool]:
        """Consume a reservation and return a guard for the reviewed claim."""
        with self._lock:
            entry = self._entries.pop(token, None)
            if (
                self._closed
                or entry is None
                or entry.name != name
                or time.monotonic() >= entry.expiry
            ):
                raise ValueError("Document reservation unavailable")
            document = entry.document

        def unchanged() -> bool:
            try:
                with self._lock:
                    return not self._closed and resolve(name) is document
            except Exception:
                return False

        return unchanged

    def clear(self) -> None:
        """Release all outstanding document references."""
        with self._lock:
            self._closed = True
            self._entries.clear()
            self._owners.clear()

    def open_owner(self, owner: str) -> None:
        """Permit captures while the authenticated socket session is live."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Document reservations are closed")
            if self._owners.get(owner) is False:
                raise RuntimeError("Document reservation session is closed")
            self._owners[owner] = True

    def discard(self, token: str) -> None:
        """Release an unclaimed token; already claimed or missing tokens are harmless."""
        if type(token) is not str:
            return
        with self._lock:
            self._entries.pop(token, None)

    def discard_capture(self, token: str) -> None:
        """Release a capture unless an admitted review owns it."""
        with self._lock:
            entry = self._entries.get(token)
            if entry is not None and not entry.admitted:
                del self._entries[token]

    def discard_owner(self, owner: str) -> None:
        """Release unclaimed reservations associated with a closed session."""
        with self._lock:
            if owner in self._owners:
                self._owners[owner] = False
            for token, entry in list(self._entries.items()):
                if entry.owner == owner:
                    del self._entries[token]

    def forget_owner(self, owner: str) -> None:
        """Remove a closed session after its socket handler exits."""
        with self._lock:
            self._owners.pop(owner, None)
            for token, entry in list(self._entries.items()):
                if entry.owner == owner:
                    del self._entries[token]
