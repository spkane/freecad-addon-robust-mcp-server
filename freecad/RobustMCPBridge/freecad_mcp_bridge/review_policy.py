"""Local policy state for reviewed actions and time-limited review bypasses.

This module has no transport or preference access. Only trusted local GUI code
may change the policy; it must not be exposed as an RPC method.
"""

from __future__ import annotations

import math
import sys
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Both MCP Python tools produce the same bridge-level action. The bridge
# cannot trust a remote client's claim that its Python came from a given tool.
REVIEWED_ACTIONS = frozenset({"execute_python"})
MAX_BYPASS_SECONDS = 8 * 60 * 60


def elapsed_clock() -> float:
    """Use a monotonic clock including sleep when the platform exposes one."""
    if sys.platform == "darwin" and hasattr(time, "CLOCK_MONOTONIC"):
        return time.clock_gettime(time.CLOCK_MONOTONIC)
    if sys.platform.startswith("linux") and hasattr(time, "CLOCK_BOOTTIME"):
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    return time.monotonic()


class ReviewPolicy:
    """Track per-action review settings and session-only monotonic bypasses."""

    def __init__(self, clock: Callable[[], float] = elapsed_clock) -> None:
        """Default every supported action to review and disable timed bypass."""
        self._clock = clock
        self._lock = threading.Lock()
        self._review_required = dict.fromkeys(REVIEWED_ACTIONS, True)
        self._allow_timed_bypass = False
        self._deadlines: dict[str, float] = {}

    def now(self) -> float:
        """Return the same clock used to issue temporary bypass deadlines."""
        return self._clock()

    @staticmethod
    def _validate_action(action: str) -> None:
        if type(action) is not str or action not in REVIEWED_ACTIONS:
            raise ValueError("Unsupported review action")

    def configure(self, action: str, *, require_review: bool) -> None:
        """Apply a locally selected action policy and revoke its timed bypass."""
        self._validate_action(action)
        if type(require_review) is not bool:
            raise TypeError("require_review must be a boolean")
        with self._lock:
            self._review_required[action] = require_review
            self._deadlines.pop(action, None)

    def set_timed_bypass_enabled(self, enabled: bool) -> None:
        """Allow or prohibit future session bypasses; disabling revokes them."""
        if type(enabled) is not bool:
            raise TypeError("enabled must be a boolean")
        with self._lock:
            self._allow_timed_bypass = enabled
            if not enabled:
                self._deadlines.clear()

    def grant_bypass(self, action: str, seconds: float) -> None:
        """Grant a bounded local session bypass for one action.

        The UI must call this only after an explicit local user decision.
        """
        self._validate_action(action)
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds)
            or not 0 < seconds <= MAX_BYPASS_SECONDS
        ):
            raise ValueError("Bypass duration must be positive and at most eight hours")
        with self._lock:
            if not self._allow_timed_bypass:
                raise PermissionError("Timed review bypass is disabled")
            self._deadlines[action] = self._clock() + seconds

    def requires_review(self, action: str) -> bool:
        """Return whether this action needs review at the instant of the check."""
        self._validate_action(action)
        with self._lock:
            deadline = self._deadlines.get(action, 0.0)
            if deadline and self._clock() >= deadline:
                self._deadlines.pop(action, None)
                deadline = 0.0
            return self._review_required[action] and not deadline

    def clear_session(self) -> None:
        """Remove all temporary bypasses on bridge stop or restart."""
        with self._lock:
            self._deadlines.clear()

    def timed_bypass_enabled(self) -> bool:
        """Return whether the local user enabled session bypass controls."""
        with self._lock:
            return self._allow_timed_bypass

    def decision(self, action: str) -> tuple[bool, float | None]:
        """Return review requirement and bypass deadline in one locked snapshot."""
        self._validate_action(action)
        with self._lock:
            deadline = self._deadlines.get(action)
            if deadline is not None and self._clock() >= deadline:
                self._deadlines.pop(action, None)
                deadline = None
            if not self._review_required[action]:
                return False, None
            return deadline is None, deadline
