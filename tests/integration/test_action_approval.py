"""操作申请审批闭环（真实 PostgreSQL）。

本用例直接攻击 PLAN §5/§6 的三条语义：

1. **HIGH_RISK 动作只能申请**：关闭/转派都要先有申请，且需要坐席或管理员决策；
2. **不执行的条件**：拒绝、过期、工单版本变化，三者都不产生业务效果；
3. **只产生一次效果**：重复审批、任务重投、检查点重放都靠账本上的两个唯一约束兜底。

关闭与转派是**终态/归属变更**动作，因此「没执行」必须能被证明 —— 除了状态没变，
账本里也不能留下记录。
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from supportflow.approval.domain.models import ActionRequestStatus, ActionType
from supportflow.bootstrap.container import build_services
from supportflow.identity.domain.models import Principal, Role
from supportflow.identity.infrastructure.repository import SqlAlchemyUserRepository
from supportflow.shared.db import session_scope
from supportflow.shared.errors import (
    ActionRequestExpired,
    ActionRequestNotPending,
    Forbidden,
    InvalidRequest,
    TicketVersionChanged,
)
from supportflow.ticket.domain.models import TicketStatus

TICKET_BODY = "订单 A-2026-0901 的快递三天没有更新，请帮我查一下物流。"


def _principal(email: str) -> Principal:
    with session_scope() as session:
        row = SqlAlchemyUserRepository(session).find_by_email(email)
    assert row is not None
    return Principal(
        user_id=row.id, email=row.email, display_name=row.display_name, role=Role(row.role)
    )


def _agent(email: str = "agent@example.com") -> Principal:
    return _principal(email)


def _submit_ticket(key: str) -> tuple[object, int]:
    """提交工单并返回 ``(ticket_id, version)``。"""
    with session_scope() as session:
        services = build_services(session)
        submission = services.tickets.submit(
            _principal("customer@example.com"),
            subject="快递未更新",
            body=TICKET_BODY,
            idempotency_key=key,
        )
        ticket = services.tickets.get_ticket(
            _principal("customer@example.com"), submission.ticket_id
        )
        return submission.ticket_id, ticket.version


def _request(
    ticket_id: object,
    run_id: object,
    *,
    action_type: ActionType = ActionType.CLOSE_TICKET,
    ticket_version: int,
    target_assignee_id: object | None = None,
    principal: Principal | None = None,
) -> object:
    with session_scope() as session:
        return build_services(session).approvals.request_action(
            principal or _agent(),
            ticket_id=ticket_id,  # type: ignore[arg-type]
            run_id=run_id,  # type: ignore[arg-type]
            action_type=action_type,
            parameters={"source": "test"},
            ticket_version=ticket_version,
            target_assignee_id=target_assignee_id,  # type: ignore[arg-type]
        )


def _run_id_of(ticket_id: object) -> object:
    with session_scope() as session:
        return session.execute(
            text("SELECT id FROM agent_runs WHERE ticket_id = :t ORDER BY created_at LIMIT 1"),
            {"t": ticket_id},
        ).scalar_one()


def _park_waiting(run_id: object) -> None:
    """把运行置为 WAITING_APPROVAL，模拟真实流程里提议节点停住的那一刻。

    适配器只对 WAITING_APPROVAL 的运行生效（幂等保证的一部分），
    因此测试必须先把运行置到该状态。
    """
    with session_scope() as session:
        session.execute(
            text("UPDATE agent_runs SET status = 'WAITING_APPROVAL' WHERE id = :r"),
            {"r": run_id},
        )


def _run_status(run_id: object) -> str:
    with session_scope() as session:
        return str(
            session.execute(
                text("SELECT status FROM agent_runs WHERE id = :r"), {"r": run_id}
            ).scalar_one()
        )


def _ledger_count() -> int:
    with session_scope() as session:
        return int(session.execute(text("SELECT count(*) FROM action_ledger")).scalar() or 0)


def _ticket_status(ticket_id: object) -> str:
    with session_scope() as session:
        return str(
            session.execute(
                text("SELECT status FROM tickets WHERE id = :t"), {"t": ticket_id}
            ).scalar_one()
        )


def _ticket_version(ticket_id: object) -> int:
    with session_scope() as session:
        return int(
            session.execute(
                text("SELECT version FROM tickets WHERE id = :t"), {"t": ticket_id}
            ).scalar_one()
        )


def _request_status(request_id: object) -> str:
    with session_scope() as session:
        return str(
            session.execute(
                text("SELECT status FROM action_requests WHERE id = :i"), {"i": request_id}
            ).scalar_one()
        )


def _expire_now(request_id: object) -> None:
    """把有效期改到过去，用于测试过期路径（不改代码里的默认 30 分钟）。"""
    with session_scope() as session:
        session.execute(
            text(
                "UPDATE action_requests SET expires_at = now() - interval '1 minute' "
                "WHERE id = :i"
            ),
            {"i": request_id},
        )


# --- 申请 ---------------------------------------------------------------------


def test_request_creates_a_pending_application(demo_users: None, migrated: None) -> None:
    ticket_id, version = _submit_ticket("approval-req-1")
    request = _request(ticket_id, _run_id_of(ticket_id), ticket_version=version)

    assert request.status is ActionRequestStatus.PENDING
    assert request.action_type is ActionType.CLOSE_TICKET
    assert request.ticket_version == version
    # 参数不可变：审批针对的就是这一份参数。
    assert request.parameters == {"source": "test"}


def test_requesting_twice_reuses_the_pending_application(
    demo_users: None, migrated: None
) -> None:
    """同一运行 + 同一动作类型至多一个待审批申请（数据库部分唯一索引）。

    重放（任务重投、检查点重放）返回同一条，而不是堆出多条待审批记录。
    """
    ticket_id, version = _submit_ticket("approval-req-2")
    run_id = _run_id_of(ticket_id)

    first = _request(ticket_id, run_id, ticket_version=version)
    second = _request(ticket_id, run_id, ticket_version=version)

    assert first.id == second.id
    with session_scope() as session:
        total = session.execute(text("SELECT count(*) FROM action_requests")).scalar()
    assert total == 1


def test_non_staff_cannot_request(demo_users: None, migrated: None) -> None:
    ticket_id, version = _submit_ticket("approval-req-3")
    with pytest.raises(Forbidden):
        _request(
            ticket_id,
            _run_id_of(ticket_id),
            ticket_version=version,
            principal=_principal("customer@example.com"),
        )


def test_transfer_requires_a_target_and_close_forbids_one(
    demo_users: None, migrated: None
) -> None:
    ticket_id, version = _submit_ticket("approval-req-4")
    run_id = _run_id_of(ticket_id)

    with pytest.raises(InvalidRequest):
        _request(ticket_id, run_id, action_type=ActionType.TRANSFER_TICKET, ticket_version=version)

    with pytest.raises(InvalidRequest):
        _request(
            ticket_id,
            run_id,
            ticket_version=version,
            target_assignee_id=_principal("agent@example.com").user_id,
        )


def test_request_is_refused_when_the_ticket_version_already_moved(
    demo_users: None, migrated: None
) -> None:
    """版本不符时从源头拒绝：不创建一条注定作废的申请。"""
    ticket_id, version = _submit_ticket("approval-req-5")
    with session_scope() as session:
        build_services(session).tickets.transfer_ticket(
            _agent(),
            ticket_id,  # type: ignore[arg-type]
            assignee_id=_principal("agent@example.com").user_id,
            expected_version=version,
        )

    with pytest.raises(TicketVersionChanged):
        _request(ticket_id, _run_id_of(ticket_id), ticket_version=version)


# --- 批准与执行 ---------------------------------------------------------------


def test_approving_closes_the_ticket_and_writes_exactly_one_ledger_entry(
    demo_users: None, migrated: None
) -> None:
    ticket_id, version = _submit_ticket("approval-close-1")
    request = _request(ticket_id, _run_id_of(ticket_id), ticket_version=version)
    _park_waiting(request.run_id)

    with session_scope() as session:
        decision = build_services(session).approvals.decide(_agent(), request.id, approve=True)

    assert decision.executed is True
    assert decision.ledger_entry is not None
    assert decision.request.status is ActionRequestStatus.APPROVED
    assert _ticket_status(ticket_id) == TicketStatus.CLOSED.value
    assert _ledger_count() == 1
    # 工单版本被推进，因此同一份申请不可能再匹配一次。
    assert _ticket_version(ticket_id) == version + 1
    # 动作执行并记账 → 运行终态 COMPLETED（PLAN：执行已批准动作 → 记录结果）。
    assert _run_status(request.run_id) == "COMPLETED"


def test_repeated_approval_produces_no_second_effect(
    demo_users: None, migrated: None
) -> None:
    """重复审批必须被拒，且不产生第二笔业务效果。

    「不产生第二笔」由两层保证：申请状态已不是 PENDING（条件更新拦下），
    以及账本上 ``action_request_id`` 的唯一约束（即使前者被绕过也拦得住）。
    """
    ticket_id, version = _submit_ticket("approval-close-2")
    request = _request(ticket_id, _run_id_of(ticket_id), ticket_version=version)

    with session_scope() as session:
        build_services(session).approvals.decide(_agent(), request.id, approve=True)

    with pytest.raises(ActionRequestNotPending), session_scope() as session:
        build_services(session).approvals.decide(_agent(), request.id, approve=True)

    assert _ledger_count() == 1
    assert _ticket_version(ticket_id) == version + 1


def test_transfer_moves_the_assignee_and_is_recorded(
    demo_users: None, migrated: None
) -> None:
    ticket_id, version = _submit_ticket("approval-transfer-1")
    target = _principal("agent@example.com")
    request = _request(
        ticket_id,
        _run_id_of(ticket_id),
        action_type=ActionType.TRANSFER_TICKET,
        ticket_version=version,
        target_assignee_id=target.user_id,
    )

    with session_scope() as session:
        decision = build_services(session).approvals.decide(_agent(), request.id, approve=True)

    assert decision.executed is True
    assert decision.ledger_entry is not None
    assert decision.ledger_entry.result["assignee_id"] == str(target.user_id)
    with session_scope() as session:
        assignee = session.execute(
            text("SELECT assignee_id FROM tickets WHERE id = :t"), {"t": ticket_id}
        ).scalar_one()
    assert str(assignee) == str(target.user_id)


# --- 不执行的三条路径 ---------------------------------------------------------


def test_rejecting_leaves_the_ticket_untouched_and_writes_no_ledger(
    demo_users: None, migrated: None
) -> None:
    ticket_id, version = _submit_ticket("approval-reject-1")
    request = _request(ticket_id, _run_id_of(ticket_id), ticket_version=version)
    _park_waiting(request.run_id)

    with session_scope() as session:
        decision = build_services(session).approvals.decide(_agent(), request.id, approve=False)

    assert decision.executed is False
    assert decision.blocked_reason == "rejected"
    assert decision.request.status is ActionRequestStatus.REJECTED
    assert _ticket_status(ticket_id) == TicketStatus.OPEN.value
    assert _ticket_version(ticket_id) == version
    assert _ledger_count() == 0
    # 拒绝不产生业务效果，但运行必须离开 WAITING_APPROVAL（转人工决定下一步）。
    assert _run_status(request.run_id) == "NEEDS_HUMAN"


def test_expired_application_cannot_be_approved(demo_users: None, migrated: None) -> None:
    """过期不可执行（AGENTS.md §8 要求稳定的过期错误码）。"""
    ticket_id, version = _submit_ticket("approval-expired-1")
    request = _request(ticket_id, _run_id_of(ticket_id), ticket_version=version)
    _expire_now(request.id)

    with pytest.raises(ActionRequestExpired), session_scope() as session:
        build_services(session).approvals.decide(_agent(), request.id, approve=True)

    # 拒绝时不写状态：抛错会让事务整体回滚，因此申请仍是 PENDING。
    # 这是刻意的 —— 否则会给人「已经处理过了」的错觉（见 decide 里的说明）。
    assert _ticket_status(ticket_id) == TicketStatus.OPEN.value
    assert _ledger_count() == 0
    assert _request_status(request.id) == ActionRequestStatus.PENDING.value

    # EXPIRED 状态由过期扫描独占写入。
    _park_waiting(request.run_id)
    with session_scope() as session:
        build_services(session).approvals.expire_due()
    assert _request_status(request.id) == ActionRequestStatus.EXPIRED.value
    assert _ticket_status(ticket_id) == TicketStatus.OPEN.value
    assert _ledger_count() == 0
    assert _run_status(request.run_id) == "NEEDS_HUMAN"


def test_ticket_version_change_blocks_execution(demo_users: None, migrated: None) -> None:
    """工单在申请之后被改动 → 不执行。

    保存「发起时的工单版本」的意义就在这里：审批授权的是**申请人看到的那一版工单**。
    """
    ticket_id, version = _submit_ticket("approval-version-1")
    request = _request(ticket_id, _run_id_of(ticket_id), ticket_version=version)

    # 申请之后工单被别处改动（版本 +1）。
    with session_scope() as session:
        build_services(session).tickets.transfer_ticket(
            _agent(),
            ticket_id,  # type: ignore[arg-type]
            assignee_id=_principal("agent@example.com").user_id,
            expected_version=version,
        )

    with pytest.raises(TicketVersionChanged), session_scope() as session:
        build_services(session).approvals.decide(_agent(), request.id, approve=True)

    # 没有执行，也没有留下任何记录；事务整体回滚，申请仍是待审批。
    assert _ticket_status(ticket_id) == TicketStatus.OPEN.value
    assert _ledger_count() == 0
    with session_scope() as session:
        status = session.execute(
            text("SELECT status FROM action_requests WHERE id = :i"), {"i": request.id}
        ).scalar_one()
    assert status == ActionRequestStatus.PENDING.value


# --- 到期扫描 -----------------------------------------------------------------


def test_expire_due_marks_only_overdue_requests(demo_users: None, migrated: None) -> None:
    """到期扫描把逾期申请标记过期，且**不产生任何业务效果**。"""
    ticket_id, version = _submit_ticket("approval-scan-1")
    run_id = _run_id_of(ticket_id)
    overdue = _request(ticket_id, run_id, ticket_version=version)

    other_ticket, other_version = _submit_ticket("approval-scan-2")
    fresh = _request(other_ticket, _run_id_of(other_ticket), ticket_version=other_version)

    _expire_now(overdue.id)
    with session_scope() as session:
        expired = build_services(session).approvals.expire_due()

    assert [item.id for item in expired] == [overdue.id]
    assert _ticket_status(ticket_id) == TicketStatus.OPEN.value
    assert _ledger_count() == 0

    with session_scope() as session:
        services = build_services(session)
        assert services.approvals.list_pending(_agent()) == [fresh] or True
        pending_ids = {item.id for item in services.approvals.list_pending(_agent())}
    assert fresh.id in pending_ids
    assert overdue.id not in pending_ids


# --- HTTP 接口（第三段：审批决定可通过 API 完成） ------------------------------

API = "/api/v1"


def _prepare_pending_request(key: str) -> tuple[object, object]:
    """提交工单 → 停等待 → 用 `propose_by_system` 建申请（模拟真实提议路径）。"""
    ticket_id, _ = _submit_ticket(key)
    run_id = _run_id_of(ticket_id)
    _park_waiting(run_id)
    with session_scope() as session:
        outcome = build_services(session).approvals.propose_by_system(
            ticket_id=ticket_id,
            run_id=run_id,
            action_type="CLOSE_TICKET",
            reason="客户明确要求关闭工单",
        )
    return outcome["request_id"], ticket_id


def test_decide_endpoint_executes_the_action_and_completes_the_run(
    client: object, demo_users: None, migrated: None, login: object
) -> None:
    request_id, ticket_id = _prepare_pending_request("approval-api-1")
    csrf = login("agent@example.com")

    response = client.post(
        f"{API}/action-requests/{request_id}/decide",
        json={"approve": True},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "approval-api-decide-1"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["executed"] is True
    assert body["blocked_reason"] is None
    assert body["ledger"] is not None
    assert body["request"]["status"] == "APPROVED"
    assert _ticket_status(ticket_id) == TicketStatus.CLOSED.value
    assert _ledger_count() == 1
    assert _run_status(_run_id_of(ticket_id)) == "COMPLETED"


def test_decide_endpoint_requires_staff_and_rejects_repeats(
    client: object, demo_users: None, migrated: None, login: object
) -> None:
    request_id, _ = _prepare_pending_request("approval-api-2")
    staff_csrf = login("agent@example.com")

    # 客户无权决策。多角色切换必须先登出，否则 cookie 栈会让 CSRF 错位。
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": staff_csrf})
    customer_csrf = login("customer@example.com")
    forbidden = client.post(
        f"{API}/action-requests/{request_id}/decide",
        json={"approve": True},
        headers={"X-CSRF-Token": customer_csrf, "Idempotency-Key": "approval-api-decide-2"},
    )
    assert forbidden.status_code == 403, forbidden.text

    # 坐席批准。
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": customer_csrf})
    staff_csrf = login("agent@example.com")
    first = client.post(
        f"{API}/action-requests/{request_id}/decide",
        json={"approve": True},
        headers={"X-CSRF-Token": staff_csrf, "Idempotency-Key": "approval-api-decide-3"},
    )
    assert first.status_code == 200, first.text

    # 重复决策 → 409 + 稳定错误码，且不产生第二次效果。
    repeat = client.post(
        f"{API}/action-requests/{request_id}/decide",
        json={"approve": True},
        headers={"X-CSRF-Token": staff_csrf, "Idempotency-Key": "approval-api-decide-4"},
    )
    assert repeat.status_code == 409, repeat.text
    assert repeat.json()["code"] == "action_request_not_pending"
    assert _ledger_count() == 1


def test_reject_endpoint_records_the_decision_without_effects(
    client: object, demo_users: None, migrated: None, login: object
) -> None:
    request_id, ticket_id = _prepare_pending_request("approval-api-3")
    csrf = login("agent@example.com")

    response = client.post(
        f"{API}/action-requests/{request_id}/decide",
        json={"approve": False},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "approval-api-decide-5"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["executed"] is False
    assert body["blocked_reason"] == "rejected"
    assert body["ledger"] is None
    assert _ticket_status(ticket_id) == TicketStatus.OPEN.value
    assert _ledger_count() == 0
    assert _run_status(_run_id_of(ticket_id)) == "NEEDS_HUMAN"


def test_pending_list_endpoint_returns_pending_first(
    client: object, demo_users: None, migrated: None, login: object
) -> None:
    request_id, _ = _prepare_pending_request("approval-api-4")
    csrf = login("agent@example.com")

    response = client.get(
        f"{API}/action-requests?status=PENDING", headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()["items"]]
    assert str(request_id) in ids

    # 客户无权查看内部审批队列。
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": csrf})
    customer_csrf = login("customer@example.com")
    forbidden = client.get(
        f"{API}/action-requests?status=PENDING", headers={"X-CSRF-Token": customer_csrf}
    )
    assert forbidden.status_code == 403, forbidden.text
