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
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from supportflow.agent.application.tools import MAX_TOOL_CALLS
from supportflow.agent.application.worker import AgentWorker
from supportflow.agent.domain.models import RunStatus
from supportflow.agent.infrastructure.repository import SqlAlchemyRunRepository
from supportflow.bootstrap.container import build_execution_unit, execution_unit_scope
from supportflow.model.domain.gateway import (
    ChatCompletion,
    ChatMessage,
    ChatRequest,
    ChatUsage,
    ModelMode,
)
from supportflow.shared.db import session_scope
from tests.conftest import API, parse_sse

SUBJECT = "快递一直没到"
BODY = "订单 A-2026-0901 的快递三天没有更新了，请帮我查一下物流"

#: 正常路径的节点顺序（与 graph.py 的常量一致）。
HAPPY_PATH_NODES = (
    "load_ticket",
    "classify_clean",
    "retrieve_knowledge",
    "tool_decision",
    "generate_draft",
    "validate_citations",
    "persist_result",
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

    def __init__(self, *, tool_requests: int = 0, crash_on_call: int | None = None) -> None:
        self.calls = 0
        self.classification_calls = 0
        self.decision_calls = 0
        self.draft_calls = 0
        self.tool_requests = tool_requests
        self.crash_on_call = crash_on_call

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
                body = json.dumps(
                    {"tool": "search_knowledge", "arguments": {"query": "物流"}},
                    ensure_ascii=False,
                )
            else:
                body = json.dumps({"tool": None})
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


def test_scripted_gateway_requires_known_contract() -> None:
    """替身只认识三种提示词契约；新增模型调用必须同步更新替身，避免静默走偏。"""
    gateway = ScriptedGateway()
    assert gateway.calls == 0
    with pytest.raises(AssertionError):
        gateway.complete(
            ChatRequest(messages=(ChatMessage(role="system", content="未知提示词"),))
        )
