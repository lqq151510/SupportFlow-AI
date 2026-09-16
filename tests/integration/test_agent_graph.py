"""LangGraph 状态图的五项验收场景（真实 PostgreSQL + 真实检查点）。

对应既定的 S2 验收口径：

1. Worker 在检索后崩溃，重启后从同一 ``run_id`` 的检查点恢复；
2. 已完成的节点不重复产生业务效果；
3. 工具调用到第 8 次时转入 ``NEEDS_HUMAN``；
4. 检索为空、证据不足或引用不属于本次检索结果时拒绝出稿并转人工；
5. SSE 仍从持久化的 ``run_events`` 读取，重连不触发图重新运行。

> ``_parse_sse`` 复用 ``tests.conftest.parse_sse``，避免两份解析逻辑漂移。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from supportflow.agent.application.tools import (
    ACTION_PROPOSAL_MARK,
    MAX_TOOL_CALLS,
)
from supportflow.agent.application.worker import AgentWorker
from supportflow.agent.domain.models import RunStatus, RunStepRecord
from supportflow.agent.infrastructure.repository import (
    SqlAlchemyRunRepository,
    SqlAlchemyRunStepRepository,
)
from supportflow.bootstrap.container import (
    build_execution_unit,
    build_services,
    execution_unit_scope,
)
from supportflow.identity.domain.models import Principal, Role
from supportflow.identity.infrastructure.repository import SqlAlchemyUserRepository
from supportflow.model.domain.gateway import (
    ChatCompletion,
    ChatMessage,
    ChatRequest,
    ChatUsage,
    ModelMode,
)
from supportflow.model.domain.models import ModelCapability, ModelProtocol
from supportflow.model.infrastructure.mock_gateway import MockChatGateway
from supportflow.shared.db import session_scope
from tests.conftest import API, parse_sse

SUBJECT = "快递一直没到"
BODY = "订单 A-2026-0901 的快递三天没有更新了，请帮我查一下物流"

#: 正常路径的节点顺序（与 graph.py 的常量一致）。
HAPPY_PATH_NODES = (
    "load_ticket",
    # 安全闸（AGENTS.md §5）：确定性预筛，正常工单放行。
    "security_guard",
    "classify_clean",
    "retrieve_knowledge",
    "tool_decision",
    "generate_draft",
    "validate_citations",
    "persist_result",
    # PLAN 流程的「可选操作审批」：默认模型认为无需操作，因此不会转 WAITING_APPROVAL。
    "propose_action",
)

_CLASSIFY_MARK = "工单分类助手"
_DECISION_MARK = "只读"
_DRAFT_MARK = "回复草稿"
_CLASSIFY_JSON = json.dumps(
    {"category": "DELIVERY", "confidence": 0.8, "rationale": "命中物流关键词"},
    ensure_ascii=False,
)


class ScriptedGateway:
    """可编排的模型替身：按提示词类型区分调用，可注入一次性崩溃与工具循环。

    真实模型不在本阶段验证范围内（S3 才接真实网关），这里只验证状态图的控制流。
    """

    def __init__(
        self,
        *,
        tool_requests: int = 0,
        crash_on_call: int | None = None,
        vary_query: bool = True,
        proposal: str | None = None,
    ) -> None:
        self.calls = 0
        self.classification_calls = 0
        self.decision_calls = 0
        self.draft_calls = 0
        self.proposal_calls = 0
        self.tool_requests = tool_requests
        self.crash_on_call = crash_on_call
        #: ``False`` 时每次都用同一组参数，用于验证「原地打转」保护。
        self.vary_query = vary_query
        #: 非空时提议该高风险动作（如 "request_close"），用于验证审批闭环。
        self.proposal = proposal

    @property
    def mode(self) -> ModelMode:
        return ModelMode.MOCK

    @property
    def model_name(self) -> str:
        return "scripted-v1"

    def complete(self, request: ChatRequest) -> ChatCompletion:
        self.calls += 1
        if self.crash_on_call == self.calls:
            raise RuntimeError("模拟 Worker 在检索后崩溃")

        system = request.messages[0].content
        if _CLASSIFY_MARK in system:
            self.classification_calls += 1
            body = _CLASSIFY_JSON
        elif _DECISION_MARK in system:
            self.decision_calls += 1
            if self.decision_calls <= self.tool_requests:
                # 默认每次换检索词：相同参数会被「原地打转」保护提前截断。
                query = f"物流-{self.decision_calls}" if self.vary_query else "物流"
                body = json.dumps(
                    {"tool": "search_knowledge", "arguments": {"query": query}},
                    ensure_ascii=False,
                )
            else:
                body = json.dumps({"tool": None})
        elif ACTION_PROPOSAL_MARK in system:
            self.proposal_calls = self.proposal_calls + 1
            body = (
                json.dumps({"action": self.proposal, "reason": "客户明确要求关闭"})
                if self.proposal
                else json.dumps({"action": None})
            )
        elif _DRAFT_MARK in system:
            self.draft_calls += 1
            body = "已核实物流异常，将为您补发并同步新的时效。[1]"
        else:  # pragma: no cover - 出现未知提示词说明节点新增了模型调用
            raise AssertionError(f"未知的模型请求契约：{system[:40]}")

        return ChatCompletion(
            text=body,
            model_name=self.model_name,
            mode=self.mode,
            usage=ChatUsage(prompt_tokens=1, completion_tokens=1),
        )


def _submit(client: TestClient, csrf: str, key: str) -> dict[str, str]:
    response = client.post(
        f"{API}/tickets",
        json={"subject": SUBJECT, "body": BODY},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _claim(run_id: UUID, *, owner: str = "worker-a") -> None:
    with session_scope() as session:
        claimed = SqlAlchemyRunRepository(session).claim(
            run_id, owner=owner, lease_seconds=600
        )
        assert claimed is not None


def _execute(run_id: UUID, gateway: ScriptedGateway, *, owner: str = "worker-a"):
    with session_scope() as session:
        unit = build_execution_unit(session, gateway=gateway)
        run = unit.runs.find_by_id(run_id)
        assert run is not None
        return unit.executor.execute(run, owner=owner)


def _ticket_version(ticket_id: UUID) -> int:
    with session_scope() as session:
        return int(
            session.execute(
                text("SELECT version FROM tickets WHERE id = :t"), {"t": ticket_id}
            ).scalar_one()
        )


def _event_names(client: TestClient, run_id: str) -> list[str]:
    body = client.get(f"{API}/runs/{run_id}/events").text
    return [name for _, name, _ in parse_sse(body)]


def _step_rows(run_id: UUID) -> list[tuple[int, str]]:
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT step_no, node_name FROM run_steps WHERE run_id = :run_id"
                " ORDER BY step_no"
            ),
            {"run_id": run_id},
        ).all()
    return [(int(row[0]), str(row[1])) for row in rows]


def _step_records(run_id: UUID) -> list[RunStepRecord]:
    with session_scope() as session:
        return SqlAlchemyRunStepRepository(session).list_steps(run_id)


def _duplicate_step_numbers(run_id: UUID) -> list[int]:
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT step_no FROM run_steps WHERE run_id = :run_id"
                " GROUP BY step_no HAVING count(*) > 1"
            ),
            {"run_id": run_id},
        ).all()
    return [int(row[0]) for row in rows]


def _run_worker_once(owner: str = "test-worker") -> bool:
    worker = AgentWorker(
        open_unit=execution_unit_scope,
        owner=owner,
        lease_seconds=600,
        poll_interval_seconds=0.0,
    )
    return worker.run_once()


# --- 1 & 2：崩溃恢复与「已完成的节点不重复产生业务效果」 ----------------------


def test_resume_after_crash_skips_completed_nodes_and_avoids_duplicates(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """在 ``tool_decision``（检索之后的第一个模型节点）崩溃，重启后从同一 run_id 恢复。

    关键断言不是「最终变成 COMPLETED」，而是：
    - 检索节点不再重跑（``retrieval.completed`` 只有一条）；
    - 分类节点不再重跑（``classification_calls == 1``）；
    - 步骤账本没有重复行，分类只写一次。
    """
    submitted = _submit(client, logged_in_customer, "graph-crash-key-1")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    # 第 2 次模型调用即 tool_decision：此时 load/classify/retrieve 的检查点已落库。
    crashing = ScriptedGateway(crash_on_call=2)
    with pytest.raises(RuntimeError):
        _execute(run_id, crashing)

    # 崩溃后运行保持 RUNNING（租约仍在），分类未写入。
    assert client.get(f"{API}/runs/{run_id}").json()["status"] == RunStatus.RUNNING.value
    assert client.get(f"{API}/tickets/{submitted['ticket_id']}").json()["category"] is None

    resumed = ScriptedGateway()
    outcome = _execute(run_id, resumed)

    assert outcome.status is RunStatus.COMPLETED
    # 分类没有被重跑：恢复从 tool_decision 继续。
    assert resumed.classification_calls == 0
    assert resumed.decision_calls == 1
    assert resumed.draft_calls == 1

    assert _duplicate_step_numbers(run_id) == []
    nodes = [node for _, node in _step_rows(run_id)]
    assert nodes == list(HAPPY_PATH_NODES)

    run = client.get(f"{API}/runs/{run_id}").json()
    assert run["status"] == RunStatus.COMPLETED.value
    assert run["step_count"] == len(HAPPY_PATH_NODES)
    assert client.get(f"{API}/tickets/{submitted['ticket_id']}").json()["category"] == "DELIVERY"

    # 检索只完成过一次：整条运行里不应出现第二次检索。
    assert _event_names(client, submitted["run_id"]).count("retrieval.completed") == 1


def test_resumed_run_reuses_prior_state_instead_of_restarting(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """恢复运行的上下文来自检查点：``run.started`` 不会因为恢复而重复下发。"""
    submitted = _submit(client, logged_in_customer, "graph-resume-key-1")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    with pytest.raises(RuntimeError):
        _execute(run_id, ScriptedGateway(crash_on_call=2))

    _execute(run_id, ScriptedGateway())

    names = _event_names(client, submitted["run_id"])
    assert names.count("run.started") == 1
    assert names.count("run.completed") == 1


# --- 3：工具调用上限 ---------------------------------------------------------


def test_tool_call_limit_hands_off_after_eight_calls(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """模型持续请求工具时，第 8 次之后不再执行，直接转人工。"""
    submitted = _submit(client, logged_in_customer, "graph-tool-cap-key-1")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    gateway = ScriptedGateway(tool_requests=MAX_TOOL_CALLS + 5)
    outcome = _execute(run_id, gateway)

    assert outcome.status is RunStatus.NEEDS_HUMAN
    assert outcome.error_code == "tool_call_limit"

    run = client.get(f"{API}/runs/{run_id}").json()
    assert run["status"] == RunStatus.NEEDS_HUMAN.value
    assert run["error_code"] == "tool_call_limit"
    assert run["tool_call_count"] == MAX_TOOL_CALLS

    names = _event_names(client, submitted["run_id"])
    assert names.count("tool.completed") == MAX_TOOL_CALLS
    assert names.count("run.needs_human") == 1
    # 上限触发时没有产出草稿。
    assert "draft.created" not in names
    assert client.get(f"{API}/tickets/{submitted['ticket_id']}").json()["category"] is None


# --- 4：无证据 / 引用无效 -----------------------------------------------------


def test_empty_retrieval_refuses_draft_and_hands_off(
    client: TestClient, demo_users: None, logged_in_customer: str
) -> None:
    """知识库为空：不产出草稿，标记 citation.invalid 并转人工。"""
    submitted = _submit(client, logged_in_customer, "graph-empty-evidence-1")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    outcome = _execute(run_id, ScriptedGateway())

    assert outcome.status is RunStatus.NEEDS_HUMAN
    assert outcome.error_code == "retrieval_empty"

    names = _event_names(client, submitted["run_id"])
    assert "citation.invalid" in names
    assert "draft.created" not in names
    assert names.count("run.needs_human") == 1


def test_repeated_identical_tool_request_stops_the_loop_early(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """模型反复提交**同一个**工具调用时提前结束循环，而不是耗尽上限。

    这是真实模型（glm-4-flash）暴露出来的行为：它会连续请求同一个检索词。
    提前结束不是放宽上限 —— 证据是否足够仍由引用校验判定，因此既不会掩盖证据不足，
    也不会白白烧掉额度。这里断言它**没有**走到第 8 次。
    """
    submitted = _submit(client, logged_in_customer, "graph-no-progress-1")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    gateway = ScriptedGateway(tool_requests=MAX_TOOL_CALLS + 5, vary_query=False)
    outcome = _execute(run_id, gateway)

    run = client.get(f"{API}/runs/{run_id}").json()
    assert run["tool_call_count"] < MAX_TOOL_CALLS, "重复请求没有提前截断"
    # 循环被截断后继续走草稿与引用校验：证据有效则正常完成。
    assert outcome.status is RunStatus.COMPLETED
    assert outcome.error_code is None

    details = [row.detail or "" for row in _step_records(run_id)]
    assert any("tool_no_progress" in detail for detail in details)


def test_tool_call_limit_is_not_reached_when_model_stops_asking(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """停在阈值之内仍然能出稿：上限只拦「超出」而不是「使用工具」。"""
    submitted = _submit(client, logged_in_customer, "graph-tool-ok-key-1")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    gateway = ScriptedGateway(tool_requests=2)
    outcome = _execute(run_id, gateway)

    assert outcome.status is RunStatus.COMPLETED
    assert gateway.decision_calls == 3  # 两次请求工具 + 一次收尾决策
    assert client.get(f"{API}/runs/{run_id}").json()["tool_call_count"] == 2


# --- 5：SSE 仍从持久化事件读取，重连不重跑图 ----------------------------------


def test_sse_reads_persisted_events_and_reconnect_does_not_rerun_graph(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    submitted = _submit(client, logged_in_customer, "graph-sse-key-0001")
    assert _run_worker_once() is True
    url = f"{API}/runs/{submitted['run_id']}/events"

    first = parse_sse(client.get(url).text)
    before = client.get(f"{API}/runs/{submitted['run_id']}").json()

    # 重连：事件序列必须完全一致，且不产生新的运行效果。
    second = parse_sse(client.get(url).text)
    after = client.get(f"{API}/runs/{submitted['run_id']}").json()

    assert [frame[0] for frame in first] == [frame[0] for frame in second]
    assert before["step_count"] == after["step_count"]
    assert before["status"] == after["status"] == RunStatus.COMPLETED.value

    # 步骤账本没有因为读取事件而增长。
    assert len(_step_rows(UUID(submitted["run_id"]))) == before["step_count"]


def test_last_event_id_resume_returns_only_newer_events(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    submitted = _submit(client, logged_in_customer, "graph-sse-key-0002")
    assert _run_worker_once() is True
    url = f"{API}/runs/{submitted['run_id']}/events"

    full = parse_sse(client.get(url).text)
    first_id = full[0][0]
    assert first_id is not None

    resumed = parse_sse(client.get(url, headers={"Last-Event-ID": str(first_id)}).text)
    assert [frame[0] for frame in resumed] == [frame[0] for frame in full[1:]]


def test_worker_rerun_after_completion_does_not_duplicate_effects(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """终态运行不会被再次领取，因此不会出现第二个业务效果。"""
    submitted = _submit(client, logged_in_customer, "graph-terminal-key-1")
    assert _run_worker_once() is True
    steps_after_first = _step_rows(UUID(submitted["run_id"]))

    assert _run_worker_once() is False
    assert _step_rows(UUID(submitted["run_id"])) == steps_after_first


# --- 网关按运行模式解析（防止「标记 real、实由 Mock 产出」） ------------------


class RecordingGateway(MockChatGateway):
    """记录调用次数的 Mock 网关，并给自己一个可区分的名字。"""

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label
        self.calls = 0

    @property
    def model_name(self) -> str:
        return f"recorder-{self.label}"

    def complete(self, request: ChatRequest) -> ChatCompletion:
        self.calls += 1
        return super().complete(request)


def _enable_fake_chat_config() -> None:
    """建一个启用的聊天配置，使 ``real`` 被判定为可用（无需真实上游）。"""
    with session_scope() as session:
        services = build_services(session)
        row = SqlAlchemyUserRepository(session).find_by_email("admin@example.com")
        assert row is not None
        admin = Principal(
            user_id=row.id,
            email=row.email,
            display_name=row.display_name,
            role=Role(row.role),
        )
        config = services.model_configs.create(
            admin,
            capability=ModelCapability.CHAT,
            protocol=ModelProtocol.OPENAI_COMPATIBLE,
            base_url="https://model.example.com/v1",
            model_name="fake-chat-model",
            api_key="sk-fake-config-key",
        )
        services.model_configs.enable(admin, config.id)


def _execute_with_mode_routing(
    run_id: UUID, *, owner: str = "worker-a"
) -> tuple[RecordingGateway, RecordingGateway]:
    """执行一次运行，返回 ``(mock 记录器, real 记录器)`` 供断言谁被调用过。"""
    mock_gateway = RecordingGateway("mock")
    real_gateway = RecordingGateway("real")

    def resolver(model_mode: str | None) -> MockChatGateway:
        return real_gateway if model_mode == "real" else mock_gateway

    with session_scope() as session:
        unit = build_execution_unit(session, gateway_for=resolver)
        run = unit.runs.find_by_id(run_id)
        assert run is not None
        unit.executor.execute(run, owner=owner)
    return mock_gateway, real_gateway


def test_run_mode_selects_the_gateway_not_the_deployment_default(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
    login: Callable[..., str],
) -> None:
    """运行按次指定 ``real`` 时，执行器必须真的走真实网关。

    若沿用装配期按部署默认值建的网关，一次 ``real`` 运行会被 Mock 产出 ——
    运行记录却写着 ``real``，评测数据即失真（AGENTS.md §10）。
    """
    _enable_fake_chat_config()
    submitted = _submit(client, logged_in_customer, "mode-gateway-key-1")

    # 第一次运行沿用部署默认（测试环境为 mock）。
    _claim(UUID(submitted["run_id"]))
    mock_used, real_used = _execute_with_mode_routing(UUID(submitted["run_id"]))
    assert mock_used.calls > 0
    assert real_used.calls == 0

    # 人工按次指定 real —— 现在应被接受（存在已启用的聊天配置）。
    client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": logged_in_customer})
    staff_csrf = login("agent@example.com")
    created = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/runs",
        json={"model_mode": "real"},
        headers={"X-CSRF-Token": staff_csrf, "Idempotency-Key": "mode-gateway-run-1"},
    )
    assert created.status_code == 202, created.text
    real_run_id = UUID(created.json()["id"])
    assert created.json()["model_mode"] == "real"

    _claim(real_run_id)
    mock_used_2, real_used_2 = _execute_with_mode_routing(real_run_id)
    assert real_used_2.calls > 0, "标记为 real 的运行没有走真实网关"
    assert mock_used_2.calls == 0, "标记为 real 的运行被 Mock 产出了"

    # 运行记录如实反映产物来自哪个模型。
    run = client.get(f"{API}/runs/{real_run_id}").json()
    assert run["chat_model_name"] == "recorder-real"


def test_scripted_gateway_requires_known_contract() -> None:
    """替身只认识三种提示词契约；新增模型调用必须同步更新替身，避免静默走偏。"""
    gateway = ScriptedGateway()
    assert gateway.calls == 0
    with pytest.raises(AssertionError):
        gateway.complete(
            ChatRequest(messages=(ChatMessage(role="system", content="未知提示词"),))
        )


# --- 高风险提议 → WAITING_APPROVAL（S4 审批闭环的可见行为） --------------------


def test_high_risk_proposal_parks_the_run_in_waiting_approval(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """模型提议关闭工单 → 创建待审批申请 → 运行停在 WAITING_APPROVAL。

    **不执行动作**：HIGH_RISK 动作必须经人工批准（AGENTS.md §5），
    因此工单保持 OPEN，也没有任何账本记录。
    """
    submitted = _submit(client, logged_in_customer, "approval-flow-1")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    gateway = ScriptedGateway(proposal="request_close")
    outcome = _execute(run_id, gateway)

    assert outcome.status is RunStatus.WAITING_APPROVAL
    assert gateway.proposal_calls == 1

    with session_scope() as session:
        row = session.execute(
            text(
                "SELECT id, action_type, status, parameters_json, ticket_version "
                "FROM action_requests WHERE run_id = :r"
            ),
            {"r": run_id},
        ).one()
        ticket_status = session.execute(
            text("SELECT status FROM tickets WHERE id = :t"),
            {"t": UUID(submitted["ticket_id"])},
        ).scalar_one()
        ledger = session.execute(text("SELECT count(*) FROM action_ledger")).scalar()

    request_id = UUID(str(row[0]))
    assert row[1] == "CLOSE_TICKET"
    assert row[2] == "PENDING"
    assert row[3]["reason"], "申请必须带可核验的理由"
    # 记录的是**提议时**的工单版本（分类写入已把版本推进到 2）。
    # 审批执行时以此为乐观锁：版本再变化即拒绝执行。
    assert row[4] == _ticket_version(UUID(submitted["ticket_id"]))
    # HIGH_RISK 动作未执行：工单保持 OPEN，账本为空。
    assert ticket_status == "OPEN"
    assert ledger == 0

    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT event_type, payload->>'request_id' AS req "
                "FROM run_events WHERE run_id = :r ORDER BY id"
            ),
            {"r": run_id},
        ).all()
    required = [row for row in rows if row[0] == "approval.required"]
    assert len(required) == 1, f"approval.required 事件数异常: {rows}"
    assert required[0][1] == str(request_id), f"事件里的申请 ID 不一致: {rows}"


def test_replaying_the_run_reuses_the_same_pending_request(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """任务重投/检查点重放时，同一运行的同一动作**复用同一条待审批申请**。

    数据库的部分唯一索引是最终保证；这里验证应用层不会另外造一条。
    """
    submitted = _submit(client, logged_in_customer, "approval-flow-2")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)
    _execute(run_id, ScriptedGateway(proposal="request_close"))

    # 模拟重投：把运行放回队列再执行一次。
    with session_scope() as session:
        session.execute(
            text("UPDATE agent_runs SET status = 'QUEUED' WHERE id = :i"), {"i": run_id}
        )
    _claim(run_id)
    outcome = _execute(run_id, ScriptedGateway(proposal="request_close"))

    assert outcome.status is RunStatus.WAITING_APPROVAL
    with session_scope() as session:
        count = session.execute(
            text("SELECT count(*) FROM action_requests WHERE run_id = :r"), {"r": run_id}
        ).scalar()
    assert count == 1, "重放创建了第二条申请"


def test_model_without_proposal_completes_normally(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    logged_in_customer: str,
) -> None:
    """模型认为无需操作时，运行照常完成 —— 不因新增节点而改变既有行为。"""
    submitted = _submit(client, logged_in_customer, "approval-flow-3")
    run_id = UUID(submitted["run_id"])
    _claim(run_id)

    gateway = ScriptedGateway()
    outcome = _execute(run_id, gateway)

    assert outcome.status is RunStatus.COMPLETED
    assert gateway.proposal_calls == 1
    with session_scope() as session:
        count = session.execute(text("SELECT count(*) FROM action_requests")).scalar()
    assert count == 0
