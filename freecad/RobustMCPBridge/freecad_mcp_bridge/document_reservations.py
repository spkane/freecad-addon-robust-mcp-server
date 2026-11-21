"""Bind a reviewed operation to one live FreeCAD document instance."""

from __future__ import annotations

import secrets
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class DocumentReservations:
    """Keep bounded, short-lived strong references until a review takes them.

    Reservation and claim must run on the FreeCAD GUI thread. Shutdown may
    close the registry from another thread. The opaque, single-use token
    prevents a caller from substituting a document name between selection and
    review; a retained wrapper prevents Python identity reuse after closure.
    """

    def __init__(self, capacity: int, lifetime: float = 300.0) -> None:
        """Initialize the reservation limit and lifetime in seconds."""
        if capacity < 1 or lifetime <= 0:
            raise ValueError("Invalid document reservation limits")
        self._capacity = capacity
        self._lifetime = lifetime
        self._entries: dict[str, tuple[str, Any, float]] = {}
        self._lock = threading.Lock()
        self._closed = False

    def reserve(self, name: str, document: Any) -> str:
        """Reserve the exact document selected on the GUI thread."""
        if not isinstance(name, str) or not name or document is None:
            raise ValueError("A named live document is required")
        with self._lock:
            if self._closed:
                raise RuntimeError("Document reservations are closed")
            now = time.monotonic()
            for token, (_, _, expiry) in list(self._entries.items()):
                if now >= expiry:
                    del self._entries[token]
            if len(self._entries) >= self._capacity:
                raise RuntimeError("Document reservation capacity reached")
            token = secrets.token_urlsafe(32)
            self._entries[token] = (name, document, now + self._lifetime)
            return token

    def take(
        self, token: str, name: str, resolve: Callable[[str], Any]
    ) -> Callable[[], bool]:
        """Consume a reservation and return a guard for the reviewed claim."""
        with self._lock:
            entry = self._entries.pop(token, None)
            if (
                self._closed
                or entry is None
                or entry[0] != name
                or time.monotonic() >= entry[2]
            ):
                raise ValueError("Document reservation unavailable")
            document = entry[1]

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

    def discard(self, token: str) -> None:
        """Release an unclaimed token; already claimed or missing tokens are harmless."""
        if type(token) is not str:
            return
        with self._lock:
            self._entries.pop(token, None)
