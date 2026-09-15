"""LangGraph 状态图：阶段 3 的正式运行管线。

```text
load_ticket → classify_clean → retrieve_knowledge → tool_decision ─┐
                                                  ↑                │ 仍需工具
                                                  └────────────────┘
                                                                   │ 证据足够
                                          generate_draft → validate_citations → persist_result
                                                                          └→ needs_human
```

设计约束（对应 AGENTS.md §5、§6）：

- **节点只做纯计算与「幂等可重放」的副作用**：步骤账本按 ``(run_id, step_no)`` 主键
  upsert，运行终态由执行器在图层之外统一落定。因此检查点重放不会重复产生业务效果。
- **检查点写入发生在每个节点之后**，所以崩溃恢复只重跑「未完成」的节点；已完成的节点
  不会再次调用模型、不会再次写分类。
- **工具调用上限 8 次**，超出即转人工；高风险工具永远不在只读循环里执行。
- 检索为空、证据不足或引用不属于本次检索结果时，不产出可交付草稿，直接转人工。
- SSE 事件名沿用阶段 2 契约，前端无需改动。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from supportflow.agent.application.drafting import (
    EVIDENCE_LIMIT,
    build_draft_request,
)
from supportflow.agent.application.drafting import (
    validate_citations as check_citations,
)
from supportflow.agent.application.ports import (
    KnowledgeRetrievalPort,
    TicketGatewayPort,
)
from supportflow.agent.application.retry import with_retries
from supportflow.agent.application.tools import (
    MAX_TOOL_CALLS,
    ToolDecision,
    build_tool_decision_request,
    parse_tool_decision,
)
from supportflow.agent.domain.models import (
    RunEventType,
    RunStatus,
    RunStepRecord,
)
from supportflow.agent.domain.ports import (
    RunEventRepositoryPort,
    RunRepositoryPort,
    RunStepRepositoryPort,
)
from supportflow.model.domain.gateway import ChatModelGateway
from supportflow.shared.errors import (
    ModelResponseInvalid,
    ModelUnavailable,
)
from supportflow.ticket.application.catalog import parse_category

logger = logging.getLogger(__name__)

NODE_LOAD = "load_ticket"
NODE_CLASSIFY = "classify_clean"
NODE_RETRIEVE = "retrieve_knowledge"
NODE_TOOL_DECISION = "tool_decision"
NODE_GENERATE = "generate_draft"
NODE_VALIDATE = "validate_citations"
NODE_PERSIST = "persist_result"
NODE_NEEDS_HUMAN = "needs_human"

#: 状态机内部的终态标记，落到 ``agent_runs.status`` 时映射为 RunStatus。
STATE_RUNNING = "RUNNING"
STATE_COMPLETED = "COMPLETED"
STATE_NEEDS_HUMAN = "NEEDS_HUMAN"
STATE_FAILED = "FAILED"
STATE_LEASE_LOST = "LEASE_LOST"

LEASE_LOST = "lease_lost"


class AgentGraphState(TypedDict, total=False):
    """图状态。只存纯量：检查点会把它序列化进 PostgreSQL 的 JSONB 列。"""

    run_id: str
    ticket_id: str
    owner: str
    model_mode: str

    ticket_no: str
    subject: str
    body_cleaned: str

    category: str
    category_confidence: float
    category_rationale: str

    evidence: list[dict[str, Any]]
    tool_calls: int
    tool_trace: list[dict[str, Any]]
    tool_signatures: list[str]
    tool_loop: bool

    draft_text: str
    citations: list[dict[str, Any]]

    next_step_no: int
    status: str
    handoff_reason: str
    error_code: str
    model_name: str
    detail: str


@dataclass(frozen=True, slots=True)
class GraphDeps:
    """一次运行所需的协作者与配置。

    ``commit`` 是节点的事务边界：每个节点结束时提交步骤账本、事件与业务写入，
    LangGraph 随后才写检查点。崩溃时未提交的节点整体回滚，因此重放不会留下半成品。
    """

    gateway: ChatModelGateway
    retrieval: KnowledgeRetrievalPort
    tickets: TicketGatewayPort
    runs: RunRepositoryPort
    events: RunEventRepositoryPort
    steps: RunStepRepositoryPort
    commit: Callable[[], None]
    max_attempts: int
    base_delay_seconds: float = 0.0
    sleeper: Callable[[float], None] = time.sleep
    retrieval_limit: int = EVIDENCE_LIMIT


@dataclass(frozen=True, slots=True)
class StepScope:
    """一个节点的步骤账本边界。"""

    step_no: int
    started_at: float
    node: str


def _begin_step(deps: GraphDeps, state: AgentGraphState, node: str) -> StepScope:
    step_no = int(state.get("next_step_no", 1))
    deps.events.append(
        UUID(state["run_id"]),
        RunEventType.STEP_STARTED,
        {"step_no": step_no, "node": node},
    )
    return StepScope(step_no=step_no, started_at=time.perf_counter(), node=node)


def _end_step(
    deps: GraphDeps, state: AgentGraphState, scope: StepScope, detail: str
) -> dict[str, object]:
    latency_ms = int((time.perf_counter() - scope.started_at) * 1000)
    run_id = UUID(state["run_id"])
    deps.steps.upsert(
        run_id,
        RunStepRecord(
            step_no=scope.step_no,
            node_name=scope.node,
            latency_ms=latency_ms,
            detail=detail[:400],
        ),
    )
    deps.events.append(
        run_id,
        RunEventType.STEP_COMPLETED,
        {"step_no": scope.step_no, "node": scope.node, "latency_ms": latency_ms},
    )
    # 事务边界：本次节点产生的步骤、事件与业务写入在此一并提交。
    deps.commit()
    return {"next_step_no": scope.step_no + 1}


def _failed(code: str, detail: str) -> dict[str, object]:
    return {"status": STATE_FAILED, "error_code": code, "detail": detail[:400]}


def _handoff(reason: str, detail: str) -> dict[str, object]:
    return {"status": STATE_NEEDS_HUMAN, "handoff_reason": reason, "detail": detail[:400]}


def _owns(deps: GraphDeps, state: AgentGraphState) -> bool:
    run = deps.runs.find_by_id(UUID(state["run_id"]))
    return (
        run is not None
        and run.status is RunStatus.RUNNING
        and run.lease_owner == state["owner"]
    )


# --- 节点 -------------------------------------------------------------------


def load_ticket(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    scope = _begin_step(deps, state, NODE_LOAD)
    facts = deps.tickets.facts(UUID(state["ticket_id"]))
    if facts is None:
        # 工单在运行期间被删除：这是不变量被破坏，不是「需要人工判断」。
        return {
            **_end_step(deps, state, scope, "ticket_missing"),
            **_failed("ticket_missing", "工单不存在"),
        }
    return {
        **_end_step(
            deps,
            state,
            scope,
            f"ticket_no={facts.ticket_no} clean_version={facts.clean_version}",
        ),
        "ticket_no": facts.ticket_no,
        "subject": facts.subject,
        "body_cleaned": facts.body_cleaned,
    }


def classify_clean(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    scope = _begin_step(deps, state, NODE_CLASSIFY)
    from supportflow.agent.application.classification import (
        build_request,
        parse_classification,
    )

    try:
        completion = with_retries(
            lambda: deps.gateway.complete(
                build_request(subject=state["subject"], body_cleaned=state["body_cleaned"])
            ),
            attempts=deps.max_attempts,
            base_delay_seconds=deps.base_delay_seconds,
            retry_on=(ModelUnavailable,),
            sleeper=deps.sleeper,
            label="classify",
        )
        outcome = parse_classification(completion.text)
    except ModelResponseInvalid as exc:
        # 非法枚举不重试、不猜测；持续失败转人工（AGENTS.md §9）。
        return {
            **_end_step(deps, state, scope, f"model_response_invalid: {exc}"),
            **_handoff("model_response_invalid", str(exc)),
        }
    except ModelUnavailable as exc:
        return {
            **_end_step(deps, state, scope, "model_unavailable"),
            **_handoff("model_unavailable", str(exc)),
        }

    return {
        **_end_step(
            deps,
            state,
            scope,
            f"{outcome.category.value} confidence={outcome.confidence}",
        ),
        "category": outcome.category.value,
        "category_confidence": outcome.confidence,
        "category_rationale": outcome.rationale,
        "model_name": completion.model_name,
    }


def retrieve_knowledge(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    scope = _begin_step(deps, state, NODE_RETRIEVE)
    query = f"{state['subject']}\n{state['body_cleaned']}"
    evidence = deps.retrieval.retrieve_for_run(query, limit=deps.retrieval_limit)
    rows = [item.as_state() for item in evidence]
    deps.events.append(
        UUID(state["run_id"]),
        RunEventType.RETRIEVAL_COMPLETED,
        {
            "query": query[:200],
            "count": len(rows),
            "full_text_hits": sum(1 for row in rows if row.get("full_text_rank") is not None),
            "vector_hits": sum(1 for row in rows if row.get("vector_rank") is not None),
        },
    )
    return {**_end_step(deps, state, scope, f"evidence={len(rows)}"), "evidence": rows}


def tool_decision(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    """决定并按需执行一个**只读**工具；每轮迭代写一条步骤账本。

    工具执行与决策合并在同一节点，这样图上只有一个 ``tool_decision`` 节点，
    与既定节点命名保持一致；循环次数由 ``MAX_TOOL_CALLS`` 封顶。
    """
    scope = _begin_step(deps, state, NODE_TOOL_DECISION)
    run_id = UUID(state["run_id"])
    calls = int(state.get("tool_calls", 0))

    try:
        completion = with_retries(
            lambda: deps.gateway.complete(
                build_tool_decision_request(
                    subject=state["subject"],
                    body_cleaned=state["body_cleaned"],
                    category=state.get("category", ""),
                    evidence_count=len(state.get("evidence", [])),
                    remaining_calls=MAX_TOOL_CALLS - calls,
                )
            ),
            attempts=deps.max_attempts,
            base_delay_seconds=deps.base_delay_seconds,
            retry_on=(ModelUnavailable,),
            sleeper=deps.sleeper,
            label="tool_decision",
        )
        decision: ToolDecision = parse_tool_decision(completion.text)
    except ModelResponseInvalid as exc:
        return {
            **_end_step(deps, state, scope, f"tool_decision_invalid: {exc}"),
            **_handoff("tool_decision_invalid", str(exc)),
        }
    except ModelUnavailable as exc:
        return {
            **_end_step(deps, state, scope, "model_unavailable"),
            **_handoff("model_unavailable", str(exc)),
        }

    if decision.tool is None:
        # 模型认为证据已足够：结束工具循环，进入草稿生成。
        return {
            **_end_step(deps, state, scope, "no_tool_requested"),
            "tool_calls": calls,
            "tool_loop": False,
            "status": STATE_RUNNING,
        }

    seen = list(state.get("tool_signatures", []))
    if decision.signature() in seen:
        # 模型在原地打转：同样的工具 + 同样的参数不会带来新信息。
        # 这里**不是放宽上限**，而是提前结束循环 —— 证据是否足够仍由引用校验判定，
        # 因此既不会掩盖证据不足，也不会白白烧掉额度。
        return {
            **_end_step(
                deps, state, scope, f"tool_no_progress: repeated {decision.tool}"
            ),
            "tool_calls": calls,
            "tool_loop": False,
            "status": STATE_RUNNING,
        }

    if calls >= MAX_TOOL_CALLS:
        # 上限是硬边界：不再执行第 9 次调用，也不静默放宽。
        return {
            **_end_step(deps, state, scope, f"tool_call_limit reached at {calls}"),
            **_handoff(
                "tool_call_limit",
                f"工具调用已达上限 {MAX_TOOL_CALLS} 次，转人工",
            ),
        }

    deps.events.append(
        run_id,
        RunEventType.TOOL_REQUESTED,
        {"tool": decision.tool, "arguments": decision.arguments, "call_no": calls + 1},
    )
    started = time.perf_counter()
    evidence = _execute_tool(deps, state, decision)
    latency_ms = int((time.perf_counter() - started) * 1000)
    deps.events.append(
        run_id,
        RunEventType.TOOL_COMPLETED,
        {
            "tool": decision.tool,
            "call_no": calls + 1,
            "latency_ms": latency_ms,
            "evidence_count": len(evidence),
        },
    )
    trace = [*state.get("tool_trace", []), {"tool": decision.tool, "call_no": calls + 1}]
    return {
        **_end_step(deps, state, scope, f"tool={decision.tool} call_no={calls + 1}"),
        "tool_calls": calls + 1,
        "tool_trace": trace,
        "tool_signatures": [*seen, decision.signature()],
        "evidence": evidence,
        "tool_loop": True,
        "status": STATE_RUNNING,
    }


def _execute_tool(
    deps: GraphDeps, state: AgentGraphState, decision: ToolDecision
) -> list[dict[str, Any]]:
    """只读工具的统一执行入口。身份与工单归属来自状态，模型参数只作检索词。"""
    if decision.tool == "search_knowledge":
        query = decision.arguments.get("query") or state["body_cleaned"]
        found = deps.retrieval.retrieve_for_run(query, limit=deps.retrieval_limit)
        return [item.as_state() for item in found]
    if decision.tool == "get_current_ticket":
        # 工单事实已在 load_ticket 注入，这里不重新读取，避免模型影响数据来源。
        return list(state.get("evidence", []))
    raise AssertionError(f"未实现的只读工具：{decision.tool!r}")


def generate_draft(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    scope = _begin_step(deps, state, NODE_GENERATE)
    evidence = list(state.get("evidence", []))
    try:
        completion = with_retries(
            lambda: deps.gateway.complete(
                build_draft_request(
                    subject=state["subject"],
                    body_cleaned=state["body_cleaned"],
                    category=state.get("category", ""),
                    evidence=evidence,
                )
            ),
            attempts=deps.max_attempts,
            base_delay_seconds=deps.base_delay_seconds,
            retry_on=(ModelUnavailable,),
            sleeper=deps.sleeper,
            label="generate_draft",
        )
    except ModelUnavailable as exc:
        return {
            **_end_step(deps, state, scope, "model_unavailable"),
            **_handoff("model_unavailable", str(exc)),
        }
    return {
        **_end_step(deps, state, scope, f"draft_chars={len(completion.text)}"),
        "draft_text": completion.text,
        "model_name": completion.model_name,
    }


def validate_citations(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    scope = _begin_step(deps, state, NODE_VALIDATE)
    evidence = list(state.get("evidence", []))
    # 引用只从本次检索结果中挑选，模型无法自行声明来源。
    citations = evidence[: deps.retrieval_limit]
    check = check_citations(
        draft_text=state.get("draft_text", ""),
        citations=citations,
        retrieval=evidence,
    )
    if not check.ok:
        deps.events.append(
            UUID(state["run_id"]),
            RunEventType.CITATION_INVALID,
            {"reason": check.reason, "invalid_markers": list(check.invalid_markers)},
        )
        return {
            **_end_step(deps, state, scope, f"citation_invalid: {check.reason}"),
            **_handoff(check.reason or "citation_invalid", "引用校验未通过"),
        }

    return {
        **_end_step(deps, state, scope, f"citations={len(citations)}"),
        "citations": citations,
        "status": STATE_RUNNING,
    }


def persist_result(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    """写回分类结果。租约已失效时放弃写回 —— 这是「至多一次业务效果」的最后一道闸。"""
    scope = _begin_step(deps, state, NODE_PERSIST)
    if not _owns(deps, state):
        logger.warning("租约已被接管，放弃写回: run_id=%s", state["run_id"])
        return {**_end_step(deps, state, scope, "lease_lost"), "status": STATE_LEASE_LOST}

    category = parse_category(state.get("category", ""))
    if category is None:  # pragma: no cover - 分类节点已经校验过枚举
        return {
            **_end_step(deps, state, scope, "category_invalid"),
            **_failed("category_invalid", "分类结果为空"),
        }

    deps.tickets.assign_category(UUID(state["ticket_id"]), category)
    deps.events.append(
        UUID(state["run_id"]),
        RunEventType.DRAFT_CREATED,
        {
            "category": category.value,
            "citation_count": len(state.get("citations", [])),
            "draft_chars": len(state.get("draft_text", "")),
        },
    )
    return {
        **_end_step(deps, state, scope, f"category={category.value}"),
        "status": STATE_COMPLETED,
    }


def needs_human(deps: GraphDeps, state: AgentGraphState) -> dict[str, object]:
    scope = _begin_step(deps, state, NODE_NEEDS_HUMAN)
    reason = state.get("handoff_reason", "unknown")
    return {
        **_end_step(deps, state, scope, f"handoff={reason}"),
        "status": STATE_NEEDS_HUMAN,
    }


# --- 路由 -------------------------------------------------------------------


def _after_load(state: AgentGraphState) -> str:
    # 工单不存在属于不变量被破坏：直接失败，不占用人工队列。
    return END if state.get("status") == STATE_FAILED else NODE_CLASSIFY


def _after_classify(state: AgentGraphState) -> str:
    return NODE_NEEDS_HUMAN if state.get("status") == STATE_NEEDS_HUMAN else NODE_RETRIEVE


def _after_retrieve(state: AgentGraphState) -> str:
    return NODE_TOOL_DECISION


def _after_tool_decision(state: AgentGraphState) -> str:
    if state.get("status") == STATE_NEEDS_HUMAN:
        return NODE_NEEDS_HUMAN
    # 刚执行完一个工具 → 再决策一次；模型不再请求工具 → 进入草稿生成。
    return NODE_TOOL_DECISION if state.get("tool_loop") else NODE_GENERATE


def _after_validate(state: AgentGraphState) -> str:
    return NODE_PERSIST if state.get("status") == STATE_RUNNING else NODE_NEEDS_HUMAN


def build_graph(deps: GraphDeps) -> StateGraph[AgentGraphState]:
    """装配并编译状态图。调用方负责传入 checkpointer 与 thread_id。"""
    graph = StateGraph(AgentGraphState)
    graph.add_node(NODE_LOAD, lambda state: load_ticket(deps, state))
    graph.add_node(NODE_CLASSIFY, lambda state: classify_clean(deps, state))
    graph.add_node(NODE_RETRIEVE, lambda state: retrieve_knowledge(deps, state))
    graph.add_node(NODE_TOOL_DECISION, lambda state: tool_decision(deps, state))
    graph.add_node(NODE_GENERATE, lambda state: generate_draft(deps, state))
    graph.add_node(NODE_VALIDATE, lambda state: validate_citations(deps, state))
    graph.add_node(NODE_PERSIST, lambda state: persist_result(deps, state))
    graph.add_node(NODE_NEEDS_HUMAN, lambda state: needs_human(deps, state))

    graph.add_edge(START, NODE_LOAD)
    graph.add_conditional_edges(
        NODE_LOAD, _after_load, {NODE_CLASSIFY: NODE_CLASSIFY, NODE_NEEDS_HUMAN: NODE_NEEDS_HUMAN}
    )
    graph.add_conditional_edges(
        NODE_CLASSIFY,
        _after_classify,
        {NODE_RETRIEVE: NODE_RETRIEVE, NODE_NEEDS_HUMAN: NODE_NEEDS_HUMAN, END: END},
    )
    graph.add_edge(NODE_RETRIEVE, NODE_TOOL_DECISION)
    graph.add_conditional_edges(
        NODE_TOOL_DECISION,
        _after_tool_decision,
        {
            NODE_TOOL_DECISION: NODE_TOOL_DECISION,
            NODE_GENERATE: NODE_GENERATE,
            NODE_NEEDS_HUMAN: NODE_NEEDS_HUMAN,
        },
    )
    graph.add_edge(NODE_GENERATE, NODE_VALIDATE)
    graph.add_conditional_edges(
        NODE_VALIDATE,
        _after_validate,
        {NODE_PERSIST: NODE_PERSIST, NODE_NEEDS_HUMAN: NODE_NEEDS_HUMAN, END: END},
    )
    graph.add_edge(NODE_PERSIST, END)
    graph.add_edge(NODE_NEEDS_HUMAN, END)
    return graph
