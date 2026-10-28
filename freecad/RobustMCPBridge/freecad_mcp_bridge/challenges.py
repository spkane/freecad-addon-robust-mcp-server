"""Bounded, single-use challenges for bridge request authentication."""

from __future__ import annotations

import math
import secrets
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class ChallengeStore:
    """Issue short-lived, single-use challenges shared by listener threads.

    Challenges are public nonces; possession does not grant access. The caller
    must verify a client proof bound to the challenge and the request. A nonce
    is consumed before proof verification so a failed attempt cannot replay it.
    """

    def __init__(
        self,
        *,
        max_pending: int = 256,
        lifetime_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Configure the pending challenge limit and expiration interval.

        Args:
            max_pending: Maximum number of unconsumed challenges.
            lifetime_seconds: Time a challenge may remain valid.
            clock: Monotonic clock used for expiration.

        Raises:
            ValueError: If either limit is not positive.
        """
        if (
            type(max_pending) is not int
            or max_pending <= 0
            or type(lifetime_seconds) not in (int, float)
            or not math.isfinite(lifetime_seconds)
            or lifetime_seconds <= 0
        ):
            raise ValueError("Challenge limits must be positive")
        self._max_pending = max_pending
        self._lifetime_seconds = lifetime_seconds
        self._clock = clock
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(self) -> str:
        """Generate a challenge, evicting the oldest pending challenge if full.

        Returns:
            A URL-safe random challenge containing 256 bits of entropy.

        Raises:
            RuntimeError: If a unique challenge cannot be generated.
        """
        with self._lock:
            now = self._clock()
            self._pending = {
                challenge: expiry
                for challenge, expiry in self._pending.items()
                if expiry > now
            }
            for _ in range(3):
                challenge = secrets.token_urlsafe(32)
                if challenge not in self._pending:
                    if len(self._pending) >= self._max_pending:
                        del self._pending[next(iter(self._pending))]
                    self._pending[challenge] = now + self._lifetime_seconds
                    return challenge
            raise RuntimeError("Could not issue a unique bridge challenge")

    def consume(self, challenge: object) -> bool:
        """Consume a challenge atomically and report whether it was valid.

        Args:
            challenge: The nonce presented by the client.

        Returns:
            True only once, before the challenge expires.
        """
        if not isinstance(challenge, str) or len(challenge) != 43:
            return False
        with self._lock:
            expiry = self._pending.pop(challenge, None)
            return expiry is not None and self._clock() < expiry
