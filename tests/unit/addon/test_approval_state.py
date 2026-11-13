"""Test approval lifecycle, including expiry and competing decisions."""

import importlib.util
import queue
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


@pytest.fixture
def approval_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the workbench module without importing FreeCAD or Qt."""
    path = (
        Path(__file__).parents[3]
        / "freecad/RobustMCPBridge/freecad_mcp_bridge/approval.py"
    )
    spec = importlib.util.spec_from_file_location("approval_state_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_saved_approval_is_rechecked_when_claimed(approval_module: ModuleType) -> None:
    """Revocation after scheduling prevents a saved approval from executing."""
    payload = approval_module.ApprovalPayload("run_macro", b"pass")
    request = approval_module.ApprovalRequest(payload, 30)
    allowed = [True]
    assert request.approve_if_still_valid(lambda: allowed[0])
    allowed[0] = False
    assert request.consume() is None
    assert request.state == approval_module.ApprovalState.DENIED


def test_saved_approval_check_failure_denies(approval_module: ModuleType) -> None:
    """A failed persisted-policy lookup cannot authorize execution."""
    request = approval_module.ApprovalRequest(
        approval_module.ApprovalPayload("run_macro", b"pass"), 30
    )

    def fail() -> bool:
        raise OSError("unavailable")

    assert request.approve_if_still_valid(fail)
    assert request.consume() is None
    assert request.state == approval_module.ApprovalState.DENIED


def test_approval_is_bound_to_immutable_content_and_is_single_use(
    approval_module: ModuleType,
) -> None:
    """Only the exact approved payload can be claimed, once."""
    payload = approval_module.ApprovalPayload("execute_python", b"print('reviewed')")
    request = approval_module.ApprovalRequest(payload, 30)
    with pytest.raises(FrozenInstanceError):
        payload.content = b"different"
    assert request.consume() is None
    assert request.decide(approved=True)
    assert request.consume() is payload
    assert request.consume() is None
    assert not request.decide(approved=True)
    assert not request.cancel()


def test_expired_or_cancelled_approval_cannot_be_revived(
    approval_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expiry or disconnect wins over any later response or dispatch."""
    clock = [100.0]
    monkeypatch.setattr(
        approval_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    expired = approval_module.ApprovalRequest(payload, 5)
    assert expired.decide(approved=True)
    clock[0] = 105.0
    assert expired.consume() is None
    assert expired.state == approval_module.ApprovalState.EXPIRED
    assert not expired.decide(approved=True)
    cancelled = approval_module.ApprovalRequest(payload, 5)
    assert cancelled.decide(approved=True)
    assert cancelled.cancel()
    assert cancelled.consume() is None
    assert not cancelled.decide(approved=True)


def test_concurrent_claims_and_cancel_have_one_winner(
    approval_module: ModuleType,
) -> None:
    """Cancellation and competing dispatchers cannot claim twice."""
    for _ in range(40):
        payload = approval_module.ApprovalPayload("execute_python", b"pass")
        request = approval_module.ApprovalRequest(payload, 30)
        assert request.decide(approved=True)
        barrier = threading.Barrier(9)

        def claim() -> object:
            barrier.wait()  # noqa: B023
            return request.consume()  # noqa: B023

        def cancel() -> bool:
            barrier.wait()  # noqa: B023
            return request.cancel()  # noqa: B023

        with ThreadPoolExecutor(max_workers=9) as executor:
            futures = [executor.submit(claim) for _ in range(8)]
            cancelled = executor.submit(cancel)
            results = [future.result() for future in futures]
            was_cancelled = cancelled.result()
        assert sum(result is payload for result in results) == (not was_cancelled)


def test_invalid_responses_and_mutable_content_are_rejected(
    approval_module: ModuleType,
) -> None:
    """Non-boolean approvals must not be interpreted as affirmative."""
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    request = approval_module.ApprovalRequest(payload, 30)
    for invalid in ("false", 1, None):
        with pytest.raises(TypeError):
            request.decide(approved=invalid)
    assert request.consume() is None
    with pytest.raises(TypeError):
        approval_module.ApprovalRequest(
            approval_module.ApprovalPayload("execute_python", bytearray(b"pass")), 30
        )
    for timeout in (0, -1, float("inf"), float("nan"), True):
        with pytest.raises(ValueError):
            approval_module.ApprovalRequest(payload, timeout)


def test_registry_capacity_expiry_and_shutdown(
    approval_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capacity, expiration and shutdown fail closed without reviving requests."""
    clock = [100.0]
    monkeypatch.setattr(
        approval_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    registry = approval_module.ApprovalRegistry(1)
    old = registry.submit(payload, 2)
    with pytest.raises(RuntimeError, match="full"):
        registry.submit(payload, 2)
    clock[0] = 102.0
    current = registry.submit(payload, 5)
    assert not old.decide(approved=True)
    assert current.decide(approved=True)
    assert registry.schedule(current, queue.Queue())
    registry.close()
    assert registry.consume(current) is None
    assert not current.decide(approved=True)
    with pytest.raises(RuntimeError, match="closed"):
        registry.submit(payload, 5)


def test_registry_shutdown_racing_claim_is_atomic(approval_module: ModuleType) -> None:
    """A claim either precedes shutdown or is denied; it never executes twice."""
    for _ in range(40):
        registry = approval_module.ApprovalRegistry(1)
        payload = approval_module.ApprovalPayload("execute_python", b"pass")
        request = registry.submit(payload, 30)
        assert request.decide(approved=True)
        assert registry.schedule(request, queue.Queue())
        barrier = threading.Barrier(2)

        def claim() -> object:
            barrier.wait()  # noqa: B023
            return registry.consume(request)  # noqa: B023

        def close() -> None:
            barrier.wait()  # noqa: B023
            registry.close()  # noqa: B023

        with ThreadPoolExecutor(max_workers=2) as executor:
            result = executor.submit(claim)
            finished = executor.submit(close)
            claimed = result.result()
            finished.result()
        assert claimed is None or claimed is payload
        assert registry.consume(request) is None


def test_scheduled_ticket_is_inert_until_consumed(approval_module: ModuleType) -> None:
    """Closing or cancelling before execution invalidates an enqueued ticket."""
    registry = approval_module.ApprovalRegistry(2)
    pending: queue.Queue = queue.Queue(maxsize=1)
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    request = registry.submit(payload, 30)
    assert not registry.schedule(request, pending)
    assert request.decide(approved=True)
    assert registry.consume(request) is None
    assert registry.schedule(request, pending)
    assert not registry.schedule(request, pending)
    second = registry.submit(payload, 30)
    assert second.decide(approved=True)
    assert not registry.schedule(second, pending)
    assert registry.cancel(request)
    assert registry.consume(pending.get_nowait()) is None
    assert registry.schedule(second, pending)
    registry.close()
    assert registry.consume(pending.get_nowait()) is None


def test_scheduled_ticket_expires_before_dispatch(
    approval_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An approval does not survive expiry while waiting in the queue."""
    clock = [10.0]
    monkeypatch.setattr(
        approval_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    registry = approval_module.ApprovalRegistry(1)
    pending: queue.Queue = queue.Queue()
    request = registry.submit(approval_module.ApprovalPayload("execute", b"pass"), 5)
    assert request.decide(approved=True)
    assert registry.schedule(request, pending)
    clock[0] = 15.0
    assert registry.consume(pending.get_nowait()) is None
    assert request.state == approval_module.ApprovalState.EXPIRED


def test_schedule_racing_shutdown_never_leaves_usable_ticket(
    approval_module: ModuleType,
) -> None:
    """A ticket scheduled before shutdown cannot be claimed after shutdown."""
    for _ in range(40):
        registry = approval_module.ApprovalRegistry(1)
        pending: queue.Queue = queue.Queue(maxsize=1)
        request = registry.submit(
            approval_module.ApprovalPayload("execute", b"pass"), 5
        )
        assert request.decide(approved=True)
        barrier = threading.Barrier(2)

        def schedule() -> bool:
            barrier.wait()  # noqa: B023
            return registry.schedule(request, pending)  # noqa: B023

        def close() -> None:
            barrier.wait()  # noqa: B023
            registry.close()  # noqa: B023

        with ThreadPoolExecutor(max_workers=2) as executor:
            scheduled = executor.submit(schedule)
            shutdown = executor.submit(close)
            was_scheduled = scheduled.result()
            shutdown.result()
        if was_scheduled:
            assert registry.consume(pending.get_nowait()) is None
        else:
            assert pending.empty()


def test_coordinator_decision_schedules_exact_payload(
    approval_module: ModuleType,
) -> None:
    """A transport worker waits while local review controls the next action."""
    coordinator = approval_module.ReviewCoordinator(2)
    payload = approval_module.ApprovalPayload("execute_python", b"print(1)")
    request = coordinator.submit(payload, 5)
    with ThreadPoolExecutor(max_workers=1) as executor:
        waiting = executor.submit(coordinator.wait_and_schedule, request)
        assert coordinator.next_execution() is None
        assert coordinator.next_review() is request
        assert request.decide(approved=True)
        assert waiting.result(timeout=2)
    assert coordinator.next_execution() == (request.request_id, payload)
    assert coordinator.next_execution() is None
    coordinator.close()


def test_coordinator_shutdown_wakes_waiter_without_execution(
    approval_module: ModuleType,
) -> None:
    """A waiting worker exits promptly when the coordinator closes."""
    coordinator = approval_module.ReviewCoordinator(1)
    request = coordinator.submit(
        approval_module.ApprovalPayload("execute_python", b"pass"), 30
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        waiting = executor.submit(coordinator.wait_and_schedule, request)
        coordinator.close()
        assert not waiting.result(timeout=2)
    assert coordinator.next_execution() is None
    assert not request.decide(approved=True)


def test_coordinator_timeout_cannot_be_approved_late(
    approval_module: ModuleType,
) -> None:
    """Approval after the deadline does not schedule any executable content."""
    coordinator = approval_module.ReviewCoordinator(1)
    request = coordinator.submit(
        approval_module.ApprovalPayload("execute_python", b"pass"), 0.01
    )
    assert not coordinator.wait_and_schedule(request)
    assert not request.decide(approved=True)
    assert coordinator.next_review() is None
    assert coordinator.next_execution() is None


def test_duplicate_waiter_cannot_cancel_scheduled_approval(
    approval_module: ModuleType,
) -> None:
    """A repeated transport waiter cannot invalidate the first scheduled ticket."""
    coordinator = approval_module.ReviewCoordinator(1)
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    request = coordinator.submit(payload, 5)
    assert request.decide(approved=True)
    assert coordinator.wait_and_schedule(request)
    assert not coordinator.wait_and_schedule(request)
    assert coordinator.next_execution() == (request.request_id, payload)


def test_two_stage_commit_binds_identity_and_content(
    approval_module: ModuleType,
) -> None:
    """Approval alone cannot execute; only its owner can commit it once."""
    coordinator = approval_module.ReviewCoordinator(2)
    broker = approval_module.LeasedReviewBroker(coordinator, 2)
    payload = approval_module.ApprovalPayload("execute_python", b"print(1)")
    request_id = broker.begin("alice", payload, 30)
    request = coordinator.next_review()
    assert request is not None
    assert broker.status("bob", request_id) is None
    assert not broker.commit("alice", request_id)
    assert request.decide(approved=True)
    assert coordinator.next_execution() is None
    assert not broker.commit("bob", request_id)
    assert not broker.cancel("bob", request_id)
    assert broker.commit("alice", request_id)
    assert not broker.commit("alice", request_id)
    assert coordinator.next_execution() == (request_id, payload)
    assert coordinator.next_execution() is None


def test_expired_queued_ticket_status_survives_result_lookup(
    approval_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Polling a missing result must leave expiry visible to the same owner."""
    clock = [10.0]
    monkeypatch.setattr(
        approval_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    coordinator = approval_module.ReviewCoordinator(1)
    broker = approval_module.LeasedReviewBroker(coordinator, 1)
    request_id = broker.begin(
        "alice", approval_module.ApprovalPayload("execute_python", b"pass"), 5
    )
    assert coordinator.next_review().decide(approved=True)
    assert broker.commit("alice", request_id)
    clock[0] = 16.0
    assert broker.result("alice", request_id) is None
    assert broker.status("alice", request_id) is approval_module.ApprovalState.EXPIRED
    assert broker.claim_next() is None


def test_two_stage_commit_cannot_revive_expired_or_cancelled_review(
    approval_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Late commits and decisions do not dispatch after expiry or cancellation."""
    clock = [10.0]
    monkeypatch.setattr(
        approval_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    coordinator = approval_module.ReviewCoordinator(2)
    broker = approval_module.LeasedReviewBroker(coordinator, 2)
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    first = broker.begin("alice", payload, 2)
    request = coordinator.next_review()
    assert request.decide(approved=True)
    clock[0] = 12.0
    assert not broker.commit("alice", first)
    assert coordinator.next_execution() is None
    second = broker.begin("alice", payload, 2)
    request2 = coordinator.next_review()
    assert broker.cancel("alice", second)
    assert not request2.decide(approved=True)
    assert not broker.commit("alice", second)
    assert coordinator.next_execution() is None


def test_two_stage_concurrent_commits_are_single_use(
    approval_module: ModuleType,
) -> None:
    """Multiple requests cannot schedule the same approval twice."""
    coordinator = approval_module.ReviewCoordinator(1)
    broker = approval_module.LeasedReviewBroker(coordinator, 1)
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    request_id = broker.begin("alice", payload, 30)
    assert coordinator.next_review().decide(approved=True)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(lambda _: broker.commit("alice", request_id), range(8))
        )
    assert sum(results) == 1
    assert coordinator.next_execution() == (request_id, payload)
    assert coordinator.next_execution() is None


def test_cancelled_review_does_not_permanently_fill_review_queue(
    approval_module: ModuleType,
) -> None:
    """A cancelled ticket is purged when a new review needs the slot."""
    coordinator = approval_module.ReviewCoordinator(1)
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    first = coordinator.submit(payload, 30)
    assert coordinator.cancel(first)
    second = coordinator.submit(payload, 30)
    assert coordinator.next_review() is second
    coordinator.close()


def test_broker_rejects_unhashable_or_malformed_request_ids(
    approval_module: ModuleType,
) -> None:
    """Malformed protocol input cannot cause an unhandled lookup error."""
    broker = approval_module.LeasedReviewBroker(approval_module.ReviewCoordinator(1), 1)
    assert broker.status("alice", []) is None
    assert not broker.commit("alice", [])
    assert not broker.cancel("alice", [])
    with pytest.raises(ValueError):
        broker.begin("", approval_module.ApprovalPayload("execute_python", b"x"), 1)
    broker.close()


def test_broker_results_are_bound_to_owner_and_expire(
    approval_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the owner can retrieve one completed result within its retention window."""
    clock = [100.0]
    monkeypatch.setattr(
        approval_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    coordinator = approval_module.ReviewCoordinator(1)
    broker = approval_module.LeasedReviewBroker(coordinator, 1)
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    request_id = broker.begin("alice", payload, 10)
    assert coordinator.next_review().decide(approved=True)
    assert broker.commit("alice", request_id)
    assert broker.claim_next() == (request_id, payload)
    assert broker.claim_next() is None
    assert not broker.cancel("alice", request_id)
    assert broker.result("alice", request_id) is None
    result: dict[str, Any] = {"success": True, "result": {"value": 3}}
    assert broker.finish(request_id, result)
    assert not broker.finish(request_id, result)
    assert broker.status("alice", request_id) == approval_module.ApprovalState.COMPLETED
    assert broker.result("bob", request_id) is None
    result["result"]["value"] = 4
    assert broker.result("alice", request_id)["result"] == {"value": 3}
    clock[0] += 60
    assert broker.result("alice", request_id) is None
    assert broker.status("alice", request_id) is None


def test_disconnect_discards_running_result(approval_module: ModuleType) -> None:
    """Disconnect cannot stop already claimed code but prevents result retention."""
    coordinator = approval_module.ReviewCoordinator(1)
    broker = approval_module.LeasedReviewBroker(coordinator, 1)
    payload = approval_module.ApprovalPayload("execute_python", b"pass")
    request_id = broker.begin("alice", payload, 30)
    assert coordinator.next_review().decide(approved=True)
    assert broker.commit("alice", request_id)
    assert broker.claim_next() == (request_id, payload)
    broker.cancel_owner("alice")
    assert not broker.finish(request_id, {"success": True})
    assert broker.result("alice", request_id) is None


def test_broker_reports_denial_to_owner_without_dispatch(
    approval_module: ModuleType,
) -> None:
    """Polling a denied request does not silently remove its result first."""
    coordinator = approval_module.ReviewCoordinator(1)
    broker = approval_module.LeasedReviewBroker(coordinator, 1)
    review_id = broker.begin(
        "alice", approval_module.ApprovalPayload("execute_python", b"pass"), 30
    )
    assert coordinator.next_review().decide(approved=False)
    assert broker.status("alice", review_id) == approval_module.ApprovalState.DENIED
    assert broker.status("bob", review_id) is None
    assert not broker.commit("alice", review_id)
    assert coordinator.next_execution() is None


def test_claim_expires_during_saved_approval_validation(
    approval_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow validation cannot authorize a request after its deadline."""
    clock = [10.0]
    monkeypatch.setattr(
        approval_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    request = approval_module.ApprovalRequest(
        approval_module.ApprovalPayload("run_macro", b"pass"), 1
    )

    def validate() -> bool:
        clock[0] = 11.0
        return True

    assert request.approve_if_still_valid(validate)
    assert request.consume() is None
    assert request.state == approval_module.ApprovalState.EXPIRED
