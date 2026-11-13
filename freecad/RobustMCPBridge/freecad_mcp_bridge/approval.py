"""Single-use approval state for local bridge execution review.

The GUI review controller and bridge queue use these primitives to bind an
approval to exact content. The separate legacy execute endpoint is not guarded.
All state transitions are protected by locks.
"""

from __future__ import annotations

import copy
import math
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class ApprovalState(str, Enum):
    """Lifecycle of one locally reviewed action."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ApprovalPayload:
    """Immutable operation and exact content presented for review."""

    action: str
    content: bytes
    macro_path: str | None = None
    macro_sha256: str | None = None
    macro_args_json: str | None = None


class ApprovalRequest:
    """Track one approval without allowing replay or revival after expiry.

    Decisions and execution claims share a lock. Expiry applies to the entire
    approval window, including time between approval and claim. A consumed
    request represents a claim to dispatch, not completion of execution.
    """

    def __init__(self, payload: ApprovalPayload, timeout_seconds: float) -> None:
        """Create a pending request with a monotonic deadline.

        Raises:
            ValueError: If the timeout is not a finite positive number.
            TypeError: If the payload is not an immutable approval payload.
        """
        if (
            type(payload) is not ApprovalPayload
            or type(payload.action) is not str
            or type(payload.content) is not bytes
            or (payload.macro_path is not None and type(payload.macro_path) is not str)
            or (
                payload.macro_sha256 is not None
                and type(payload.macro_sha256) is not str
            )
            or (
                payload.macro_args_json is not None
                and type(payload.macro_args_json) is not str
            )
        ):
            raise TypeError("Approval payload must contain immutable bytes")
        if (
            isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("Approval timeout must be finite and positive")
        self._payload = payload
        self._request_id = str(uuid.uuid4())
        self._deadline = time.monotonic() + timeout_seconds
        self._bypass_deadline: float | None = None
        self._bypass_clock: Callable[[], float] | None = None
        self._claim_validator: Callable[[], bool] | None = None
        self._state = ApprovalState.PENDING
        self._lock = threading.Lock()
        self._decision_event = threading.Event()

    @property
    def request_id(self) -> str:
        """Return the local request identifier."""
        return self._request_id

    @property
    def payload(self) -> ApprovalPayload:
        """Return the immutable payload displayed for review."""
        return self._payload

    def _expire_locked(self) -> None:
        if self._state in (
            ApprovalState.PENDING,
            ApprovalState.APPROVED,
        ) and (
            time.monotonic() >= self._deadline
            or (
                self._bypass_deadline is not None
                and self._bypass_clock is not None
                and self._bypass_clock() >= self._bypass_deadline
            )
        ):
            self._state = ApprovalState.EXPIRED
            self._decision_event.set()

    @property
    def state(self) -> ApprovalState:
        """Return current state after applying the deadline."""
        with self._lock:
            self._expire_locked()
            return self._state

    def decide(self, *, approved: bool) -> bool:
        """Accept a local decision once; reject late or repeated decisions."""
        if type(approved) is not bool:
            raise TypeError("Approval decision must be a boolean")
        with self._lock:
            self._expire_locked()
            if self._state is not ApprovalState.PENDING:
                return False
            self._state = ApprovalState.APPROVED if approved else ApprovalState.DENIED
            self._decision_event.set()
            return True

    def approve_until(self, deadline: float, clock: Callable[[], float]) -> bool:
        """Approve only until a local temporary bypass expires."""
        with self._lock:
            self._expire_locked()
            if self._state is not ApprovalState.PENDING or clock() >= deadline:
                return False
            self._bypass_deadline = deadline
            self._bypass_clock = clock
            self._state = ApprovalState.APPROVED
            self._decision_event.set()
            return True

    def approve_if_still_valid(self, validator: Callable[[], bool]) -> bool:
        """Approve provisionally, checking a local policy again at claim time."""
        if not callable(validator):
            raise TypeError("Claim validator must be callable")
        with self._lock:
            self._expire_locked()
            if self._state is not ApprovalState.PENDING:
                return False
            self._claim_validator = validator
            self._state = ApprovalState.APPROVED
            self._decision_event.set()
            return True

    def cancel(self) -> bool:
        """Deny a pending or approved request before it is consumed."""
        with self._lock:
            self._expire_locked()
            if self._state not in (ApprovalState.PENDING, ApprovalState.APPROVED):
                return False
            self._state = ApprovalState.DENIED
            self._decision_event.set()
            return True

    def wait_for_decision(self) -> ApprovalState:
        """Wait until a decision, cancellation, or the request deadline.

        This is for a transport worker, never the Qt main thread. A returned
        approval is provisional: it must still be scheduled and consumed before
        expiry, and cancellation or shutdown can invalidate it in between.
        """
        with self._lock:
            self._expire_locked()
            remaining = max(0.0, self._deadline - time.monotonic())
        self._decision_event.wait(remaining)
        return self.state

    def consume(self) -> ApprovalPayload | None:
        """Claim the exact approved payload once, or return None."""
        with self._lock:
            self._expire_locked()
            if self._state is not ApprovalState.APPROVED:
                return None
            if self._claim_validator is not None:
                try:
                    valid = self._claim_validator() is True
                except Exception:
                    valid = False
                if not valid:
                    self._state = ApprovalState.DENIED
                    return None
                self._expire_locked()
                if self._state is not ApprovalState.APPROVED:
                    return None
            self._state = ApprovalState.CONSUMED
            return self._payload


class ApprovalRegistry:
    """Bound pending requests and serialize claims against cancellation and shutdown.

    The registry is a local coordination primitive, not an authorization API.
    Only trusted UI code should receive request objects or invoke ``decide``.
    Scheduled entries are inert tickets; the consumer must call ``consume``
    immediately before execution. Closing or cancelling the registry invalidates
    queued tickets. Already consumed work cannot be stopped by this registry.
    """

    def __init__(self, max_pending: int) -> None:
        """Create a registry with an explicit positive capacity."""
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError("Approval capacity must be a positive integer")
        self._capacity = max_pending
        self._requests: dict[str, ApprovalRequest] = {}
        self._scheduled: set[str] = set()
        self._closed = False
        self._lock = threading.Lock()

    def _remove_terminal_locked(self) -> None:
        for request_id, request in list(self._requests.items()):
            if request.state not in (ApprovalState.PENDING, ApprovalState.APPROVED):
                del self._requests[request_id]
                self._scheduled.discard(request_id)

    def submit(
        self, payload: ApprovalPayload, timeout_seconds: float
    ) -> ApprovalRequest:
        """Admit a request, failing closed if closed or at capacity."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Approval registry is closed")
            self._remove_terminal_locked()
            if len(self._requests) >= self._capacity:
                raise RuntimeError("Approval registry is full")
            request = ApprovalRequest(payload, timeout_seconds)
            self._requests[request.request_id] = request
            return request

    def schedule(
        self, request: ApprovalRequest, pending: queue.Queue[ApprovalRequest]
    ) -> bool:
        """Enqueue one inert ticket after approval, without blocking.

        A queue-full error leaves the request approved and retryable until its
        deadline. The consumer must still call ``consume`` to claim the payload.
        """
        if type(pending) is not queue.Queue:
            raise TypeError("Approval queue must be a standard Queue")
        with self._lock:
            if (
                self._closed
                or self._requests.get(request.request_id) is not request
                or request.request_id in self._scheduled
                or request.state is not ApprovalState.APPROVED
            ):
                return False
            try:
                pending.put_nowait(request)
            except queue.Full:
                return False
            self._scheduled.add(request.request_id)
            return True

    def consume(self, request: ApprovalRequest) -> ApprovalPayload | None:
        """Claim a scheduled decision once, unless cancelled or shut down."""
        with self._lock:
            if (
                self._closed
                or self._requests.get(request.request_id) is not request
                or request.request_id not in self._scheduled
            ):
                return None
            payload = request.consume()
            if payload is not None or request.state in (
                ApprovalState.DENIED,
                ApprovalState.EXPIRED,
            ):
                del self._requests[request.request_id]
                self._scheduled.discard(request.request_id)
            return payload

    def cancel(self, request: ApprovalRequest) -> bool:
        """Cancel an admitted request before it has been claimed."""
        with self._lock:
            if self._requests.get(request.request_id) is not request:
                return False
            cancelled = request.cancel()
            del self._requests[request.request_id]
            self._scheduled.discard(request.request_id)
            return cancelled

    def close(self) -> None:
        """Deny outstanding requests and reject new ones permanently."""
        with self._lock:
            self._closed = True
            for request in self._requests.values():
                request.cancel()
            self._requests.clear()
            self._scheduled.clear()


class ReviewCoordinator:
    """Connect transport workers to a bounded main-thread review queue.

    This class contains no Qt or transport code. A Qt timer must call
    ``next_review`` on the main thread and retain any dialog it creates. A
    transport worker can call ``wait_and_schedule`` without blocking Qt.
    Only trusted local code may make the actual approval decision.
    """

    def __init__(self, max_pending: int) -> None:
        """Create bounded queues for pending review and execution tickets."""
        self._registry = ApprovalRegistry(max_pending)
        self._reviews: queue.Queue[ApprovalRequest] = queue.Queue(maxsize=max_pending)
        self._executions: queue.Queue[ApprovalRequest] = queue.Queue(
            maxsize=max_pending
        )
        self._workers: set[str] = set()
        self._lock = threading.Lock()
        self._closed = False

    def submit(
        self, payload: ApprovalPayload, timeout_seconds: float
    ) -> ApprovalRequest:
        """Admit a bounded request for local review or fail closed."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Review coordinator is closed")
            request = self._registry.submit(payload, timeout_seconds)
            try:
                self._reviews.put_nowait(request)
            except queue.Full:
                self._prune_reviews_locked()
                try:
                    self._reviews.put_nowait(request)
                except queue.Full:
                    self._registry.cancel(request)
                    raise RuntimeError("Review queue is full") from None
            return request

    def _prune_reviews_locked(self) -> None:
        """Discard stale review tickets without changing their relative order."""
        pending = []
        while True:
            try:
                request = self._reviews.get_nowait()
            except queue.Empty:
                break
            if request.state is ApprovalState.PENDING:
                pending.append(request)
            else:
                self._registry.cancel(request)
        for request in pending:
            self._reviews.put_nowait(request)

    def next_review(self) -> ApprovalRequest | None:
        """Get a still-pending request without waiting; call on the Qt thread."""
        while True:
            try:
                request = self._reviews.get_nowait()
            except queue.Empty:
                return None
            if request.state is ApprovalState.PENDING:
                return request
            self._registry.cancel(request)

    def wait_and_schedule(self, request: ApprovalRequest) -> bool:
        """Wait for a local decision and schedule an inert ticket if approved."""
        with self._lock:
            if self._closed or request.request_id in self._workers:
                return False
            self._workers.add(request.request_id)
        if request.wait_for_decision() is not ApprovalState.APPROVED:
            self._registry.cancel(request)
            with self._lock:
                self._workers.discard(request.request_id)
            return False
        if not self._registry.schedule(request, self._executions):
            self._registry.cancel(request)
            with self._lock:
                self._workers.discard(request.request_id)
            return False
        return True

    def next_execution(self) -> tuple[str, ApprovalPayload] | None:
        """Claim a valid ticket with its request ID, or return None without blocking."""
        while True:
            try:
                request = self._executions.get_nowait()
            except queue.Empty:
                return None
            payload = self._registry.consume(request)
            with self._lock:
                self._workers.discard(request.request_id)
            if payload is not None:
                return request.request_id, payload

    def cancel(self, request: ApprovalRequest) -> bool:
        """Deny a request if it has not yet been consumed."""
        result = self._registry.cancel(request)
        with self._lock:
            self._workers.discard(request.request_id)
        return result

    def close(self) -> None:
        """Deny and wake all pending requests; prevent further admission."""
        with self._lock:
            self._closed = True
            self._registry.close()
            self._workers.clear()


class LeasedReviewBroker:
    """Client-bound, two-stage approval without automatic execution.

    The caller must pass an identity established by bridge authentication, not
    a client-provided unverified parameter. Approval only permits a subsequent
    explicit commit by that identity; it is not a disconnect notification.
    If multiple processes share
    one credential, identity binding does not distinguish those processes.
    """

    def __init__(self, coordinator: ReviewCoordinator, max_pending: int) -> None:
        """Use the supplied review coordinator with a bounded request index."""
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError("Review capacity must be a positive integer")
        self._coordinator = coordinator
        self._capacity = max_pending
        self._entries: dict[str, tuple[str, ApprovalRequest]] = {}
        self._committed: set[str] = set()
        self._running: set[str] = set()
        self._results: dict[str, tuple[float, dict[str, object]]] = {}
        self._lock = threading.Lock()
        self._closed = False

    def _expire_locked(self) -> None:
        for request_id, (_, request) in list(self._entries.items()):
            if request_id in self._running:
                continue
            result = self._results.get(request_id)
            if result is not None and time.monotonic() < result[0]:
                continue
            if request.state in (
                ApprovalState.EXPIRED,
                ApprovalState.DENIED,
                ApprovalState.CONSUMED,
            ):
                self._coordinator.cancel(request)
                del self._entries[request_id]
                self._committed.discard(request_id)
                self._results.pop(request_id, None)

    def begin(self, principal: str, payload: ApprovalPayload, timeout: float) -> str:
        """Create a review for an already authenticated identity.

        Returns an opaque request identifier. This does not dispatch code.
        """
        if type(principal) is not str or not principal or len(principal) > 64:
            raise ValueError("A bounded authenticated client identity is required")
        with self._lock:
            if self._closed:
                raise RuntimeError("Review broker is closed")
            self._expire_locked()
            if len(self._entries) >= self._capacity:
                raise RuntimeError("Review broker is full")
            request = self._coordinator.submit(payload, timeout)
            self._entries[request.request_id] = (principal, request)
            return request.request_id

    def status(self, principal: str, request_id: str) -> ApprovalState | None:
        """Return a request state only to its authenticated owner."""
        if type(principal) is not str or type(request_id) is not str:
            return None
        with self._lock:
            entry = self._entries.get(request_id)
            if self._closed or entry is None or entry[0] != principal:
                return None
            item = self._results.get(request_id)
            if item is not None:
                if time.monotonic() >= item[0]:
                    self._expire_locked()
                    return None
                return ApprovalState.COMPLETED
            return entry[1].state

    def commit(self, principal: str, request_id: str) -> bool:
        """Schedule exactly one approved request owned by this identity."""
        if type(principal) is not str or type(request_id) is not str:
            return False
        with self._lock:
            entry = self._entries.get(request_id)
            if (
                self._closed
                or entry is None
                or entry[0] != principal
                or request_id in self._committed
            ):
                return False
            request = entry[1]
            if request.state is not ApprovalState.APPROVED:
                return False
            scheduled = self._coordinator.wait_and_schedule(request)
            if scheduled:
                self._committed.add(request_id)
            else:
                del self._entries[request_id]
            return scheduled

    def cancel(self, principal: str, request_id: str) -> bool:
        """Cancel an uncommitted review owned by this identity."""
        if type(principal) is not str or type(request_id) is not str:
            return False
        with self._lock:
            entry = self._entries.get(request_id)
            if self._closed or entry is None or entry[0] != principal:
                return False
            if request_id in self._running or request_id in self._results:
                return False
            del self._entries[request_id]
            self._committed.discard(request_id)
            return self._coordinator.cancel(entry[1])

    def cancel_owner(self, principal: str) -> None:
        """Invalidate this connection's unconsumed reviews and queued tickets."""
        with self._lock:
            for request_id, (owner, request) in list(self._entries.items()):
                if owner == principal:
                    self._coordinator.cancel(request)
                    del self._entries[request_id]
                    self._committed.discard(request_id)
                    self._running.discard(request_id)
                    self._results.pop(request_id, None)

    def claim_next(self) -> tuple[str, ApprovalPayload] | None:
        """Claim one committed ticket for the FreeCAD thread to execute once."""
        with self._lock:
            if self._closed:
                return None
            item = self._coordinator.next_execution()
            if item is None:
                return None
            request_id, payload = item
            if request_id not in self._committed or request_id not in self._entries:
                return None
            self._running.add(request_id)
            return request_id, payload

    def finish(self, request_id: str, result: dict[str, object]) -> bool:
        """Store one completed result for its owner for a bounded time."""
        with self._lock:
            if self._closed or request_id not in self._running:
                return False
            self._running.remove(request_id)
            self._results[request_id] = (time.monotonic() + 60, copy.deepcopy(result))
            return True

    def result(self, principal: str, request_id: str) -> dict[str, object] | None:
        """Read a completed result only for its authenticated owner."""
        if type(principal) is not str or type(request_id) is not str:
            return None
        with self._lock:
            entry = self._entries.get(request_id)
            item = self._results.get(request_id)
            if self._closed or entry is None or entry[0] != principal or item is None:
                return None
            if time.monotonic() >= item[0]:
                self._expire_locked()
                return None
            return copy.deepcopy(item[1])

    def close(self) -> None:
        """Deny outstanding work and disable the broker."""
        with self._lock:
            self._closed = True
            self._entries.clear()
            self._committed.clear()
            self._running.clear()
            self._results.clear()
            self._coordinator.close()
