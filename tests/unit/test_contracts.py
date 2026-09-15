"""错误码与领域模型的契约单测。

错误码是**对外契约**：前端按 ``code`` 分支，不能随意改名。这里把当前取值固定下来，
改名或改状态码都会让测试失败，从而强制走一次评审。
"""

from __future__ import annotations

import pytest

from supportflow.agent.domain.models import (
    ACTIVE_RUN_STATUSES,
    RunEventType,
    RunStatus,
)
from supportflow.shared.errors import (
    AppError,
    CsrfValidationFailed,
    Forbidden,
    IdempotencyKeyReused,
    InvalidRequest,
    ModelAuthenticationFailed,
    ModelConfigInvalid,
    ModelModeNotPermitted,
    ModelRequestRejected,
    ModelResponseInvalid,
    ModelUnavailable,
    NotFound,
    RunAlreadyActive,
    ServiceUnavailable,
    Unauthenticated,
    build_problem,
)
from supportflow.ticket.domain.models import TicketCategory, TicketStatus

EXPECTED_ERRORS: list[tuple[type[AppError], int, str]] = [
    (InvalidRequest, 400, "invalid_request"),
    (Unauthenticated, 401, "unauthenticated"),
    (Forbidden, 403, "forbidden"),
    (CsrfValidationFailed, 403, "csrf_failed"),
    (NotFound, 404, "not_found"),
    (IdempotencyKeyReused, 409, "idempotency_key_reused"),
    (RunAlreadyActive, 409, "run_already_active"),
    (ModelModeNotPermitted, 403, "model_mode_not_permitted"),
    (ModelUnavailable, 503, "model_unavailable"),
    (ModelResponseInvalid, 502, "model_response_invalid"),
    (ModelAuthenticationFailed, 502, "model_auth_failed"),
    (ModelRequestRejected, 502, "model_request_rejected"),
    (ModelConfigInvalid, 503, "model_config_invalid"),
    (ServiceUnavailable, 503, "service_unavailable"),
]


@pytest.mark.parametrize(("cls", "status", "code"), EXPECTED_ERRORS)
def test_error_codes_are_stable(cls: type[AppError], status: int, code: str) -> None:
    error = cls("细节")
    assert error.status == status
    assert error.code == code
    assert error.detail == "细节"
    assert isinstance(error, AppError)


def test_error_codes_are_unique() -> None:
    codes = [code for _, _, code in EXPECTED_ERRORS]
    assert len(codes) == len(set(codes))


def test_csrf_failure_is_a_forbidden_subclass() -> None:
    # 保持 403 语义：CSRF 失败是权限类错误，不是 400。
    assert issubclass(CsrfValidationFailed, Forbidden)


def test_extra_fields_are_carried_for_problem_details() -> None:
    error = IdempotencyKeyReused("重复键", scope="s", key="k")
    assert error.extra == {"scope": "s", "key": "k"}


def test_upstream_message_never_reaches_the_response_body() -> None:
    """上游原始诊断只供服务端与管理员诊断使用。

    它刻意放在独立属性而不是 ``extra`` 里 —— ``extra`` 会被合并进响应体，
    而 AGENTS.md §8 要求不把底层异常文本暴露给客户端。
    """
    upstream = "身份验证失败。请求 id=abc-123"
    error = ModelAuthenticationFailed("模型服务拒绝了当前凭据")
    error.upstream_message = upstream

    class _Request:
        class state:
            request_id = "req-1"

        class url:
            path = "/api/v1/model-configs/1/test"

    problem = build_problem(error, _Request())  # type: ignore[arg-type]
    dumped = problem.model_dump_json()
    assert upstream not in dumped
    assert "abc-123" not in dumped
    # 但服务端自己仍能读到它。
    assert error.upstream_message == upstream


def test_extra_does_carry_fields_into_problem_details() -> None:
    """与上一条对照：``extra`` 确实会进响应体，因此敏感信息不得放进去。"""
    error = Forbidden("无权访问", scope="tickets")
    assert error.extra["scope"] == "tickets"
    assert error.upstream_message is None


# --- 运行状态机 -------------------------------------------------------------


def test_terminal_statuses_do_not_overlap_active_statuses() -> None:
    active = set(ACTIVE_RUN_STATUSES)
    terminal = {status for status in RunStatus if status.is_terminal}
    assert active.isdisjoint(terminal)
    assert active | terminal == set(RunStatus)


@pytest.mark.parametrize(
    "status", [RunStatus.COMPLETED, RunStatus.NEEDS_HUMAN, RunStatus.FAILED]
)
def test_terminal_statuses(status: RunStatus) -> None:
    assert status.is_terminal


@pytest.mark.parametrize(
    "status", [RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING_APPROVAL]
)
def test_non_terminal_statuses(status: RunStatus) -> None:
    assert not status.is_terminal


def test_event_type_values_are_namespaced() -> None:
    namespaces = (
        "run.",
        "retrieval.",
        "tool.",
        "draft.",
        "citation.",
        "approval.",
        "action.",
    )
    for event in RunEventType:
        assert event.value.startswith(namespaces), event.value


# --- 工单状态与分类 ---------------------------------------------------------


def test_ticket_only_has_open_and_closed() -> None:
    # 单工作区模型刻意只有两个状态，CLOSED 为终态。
    assert {status.value for status in TicketStatus} == {"OPEN", "CLOSED"}


def test_ticket_category_labels_cover_all_categories() -> None:
    from supportflow.ticket.domain.models import CATEGORY_LABELS

    assert set(CATEGORY_LABELS) == set(TicketCategory)
    assert all(label for label in CATEGORY_LABELS.values())
