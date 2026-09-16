"""草稿「生成 → 编辑 → 发布」闭环的集成测试（真实 PostgreSQL）。

验收口径（PLAN §6 草稿审核页）：
1. Agent 运行完成即落一条 ACTIVE 草稿（author=agent），并随工单详情返回；
2. 坐席编辑当前 ACTIVE 草稿 → 派生新版本（author=human），旧版本归档；
3. 坐席发布当前 ACTIVE 草稿 → 置为 PUBLISHED（终态），工单详情带 ``published_reply``；
4. 已发布/已归档的草稿不可再编辑（409）；
5. 编辑与发布都需要 CSRF + 幂等键，重放返回首次结果；
6. 普通客户无权编辑/发布（403）。

会话状态不依赖夹具求值顺序：每个用例显式 ``login`` 切换身份，避免 CSRF Cookie 与令牌错位。
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi.testclient import TestClient

from supportflow.agent.application.tools import ACTION_PROPOSAL_MARK
from supportflow.agent.infrastructure.repository import SqlAlchemyRunRepository
from supportflow.bootstrap.container import build_execution_unit
from supportflow.identity.domain.models import Role
from supportflow.model.domain.gateway import (
    ChatCompletion,
    ChatRequest,
    ChatUsage,
    ModelMode,
)
from supportflow.shared.db import session_scope
from tests.conftest import API

SUBJECT = "快递一直没到"
BODY = "订单 A-2026-0901 的快递三天没有更新了，请帮我查一下物流"
DRAFT_TEXT = "已核实物流异常，将为您补发并同步新的时效。[1]"


class _HappyGateway:
    """最小可完成的模型替身：分类→不调用工具→出稿→不提议操作。"""

    @property
    def mode(self) -> ModelMode:
        return ModelMode.MOCK

    @property
    def model_name(self) -> str:
        return "draft-happy"

    def complete(self, request: ChatRequest) -> ChatCompletion:
        system = request.messages[0].content
        if "工单分类助手" in system:
            body = json.dumps(
                {"category": "DELIVERY", "confidence": 0.8, "rationale": "命中物流关键词"},
                ensure_ascii=False,
            )
        elif "只读" in system:
            body = json.dumps({"tool": None})
        elif ACTION_PROPOSAL_MARK in system:
            body = json.dumps({"action": None})
        elif "回复草稿" in system:
            body = DRAFT_TEXT
        else:  # pragma: no cover - 节点新增模型调用须同步更新
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


def _claim(run_id: UUID, owner: str = "worker-draft") -> None:
    with session_scope() as session:
        claimed = SqlAlchemyRunRepository(session).claim(run_id, owner=owner, lease_seconds=600)
        assert claimed is not None


def _run_happy_path(client: TestClient, csrf: str, key: str) -> dict[str, str]:
    submitted = _submit(client, csrf, key)
    run_id = UUID(submitted["run_id"])
    _claim(run_id)
    with session_scope() as session:
        unit = build_execution_unit(session, gateway=_HappyGateway())
        run = unit.runs.find_by_id(run_id)
        assert run is not None
        unit.executor.execute(run, owner="worker-draft")
    return submitted


def _active_draft_id(client: TestClient, ticket_id: str) -> str:
    drafts = client.get(f"{API}/tickets/{ticket_id}/drafts").json()
    active = [d for d in drafts if d["status"] == "ACTIVE"]
    assert active, f"没有 ACTIVE 草稿: {drafts}"
    return active[0]["id"]


# --- 1：运行完成即落 ACTIVE 草稿 ----------------------------------------------


def test_agent_run_persists_active_draft(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-gen-key-1")

    detail = client.get(f"{API}/tickets/{submitted['ticket_id']}").json()
    assert len(detail["drafts"]) == 1
    draft = detail["drafts"][0]
    assert draft["author"] == "agent"
    assert draft["status"] == "ACTIVE"
    assert draft["version"] == 1
    assert draft["content"] == DRAFT_TEXT
    # 引用是服务端从本次检索结果快照下来的，非空且结构化。
    assert isinstance(draft["citations"], list) and len(draft["citations"]) >= 1
    assert "source_id" in draft["citations"][0]


# --- 2：编辑派生新版本（human），旧版本归档 -----------------------------------


def test_staff_edit_creates_new_human_version_and_archives_old(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-edit-key-1")
    draft_id = _active_draft_id(client, submitted["ticket_id"])

    agent_csrf = login("agent@example.com")
    edited = client.patch(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}",
        json={"content": "核实后已为您补发，预计 3 日内送达。[1]"},
        headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "edit-key-1"},
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["author"] == "human"
    assert body["status"] == "ACTIVE"
    assert body["version"] == 2
    assert body["editor_user_id"] is not None

    drafts = client.get(f"{API}/tickets/{submitted['ticket_id']}/drafts").json()
    by_version = {d["version"]: d for d in drafts}
    assert by_version[1]["status"] == "ARCHIVED"
    assert by_version[2]["status"] == "ACTIVE"


def test_editing_requires_idempotency_key(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-edit-noidem-1")
    draft_id = _active_draft_id(client, submitted["ticket_id"])
    agent_csrf = login("agent@example.com")
    response = client.patch(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}",
        json={"content": "x"},
        headers={"X-CSRF-Token": agent_csrf},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_replaying_edit_returns_original_version(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-edit-replay-1")
    draft_id = _active_draft_id(client, submitted["ticket_id"])
    agent_csrf = login("agent@example.com")
    first = client.patch(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}",
        json={"content": "编辑内容-A"},
        headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "edit-replay-key"},
    )
    second = client.patch(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}",
        json={"content": "编辑内容-A"},
        headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "edit-replay-key"},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["version"] == second.json()["version"] == 2
    # 重放没有派生第三个版本。
    assert len(client.get(f"{API}/tickets/{submitted['ticket_id']}/drafts").json()) == 2


# --- 3：发布为正式回复 --------------------------------------------------------


def test_staff_publish_marks_draft_published_and_sets_reply(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-publish-key-1")
    draft_id = _active_draft_id(client, submitted["ticket_id"])

    agent_csrf = login("agent@example.com")
    published = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}/publish",
        headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "publish-key-1"},
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["status"] == "PUBLISHED"
    assert body["published_at"] is not None
    assert body["published_by"] is not None

    detail = client.get(f"{API}/tickets/{submitted['ticket_id']}").json()
    assert detail["published_reply"] == body["content"]


def test_cannot_edit_published_draft(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-published-edit-1")
    draft_id = _active_draft_id(client, submitted["ticket_id"])
    agent_csrf = login("agent@example.com")
    assert (
        client.post(
            f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}/publish",
            headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "pub-edit-01"},
        ).status_code
        == 200
    )
    again = client.patch(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}",
        json={"content": "再来一次编辑"},
        headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "pub-edit-1"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "conflict"


def test_publish_is_idempotent_on_replay(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-publish-replay-1")
    draft_id = _active_draft_id(client, submitted["ticket_id"])
    agent_csrf = login("agent@example.com")
    first = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}/publish",
        headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "pub-replay-key"},
    )
    second = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}/publish",
        headers={"X-CSRF-Token": agent_csrf, "Idempotency-Key": "pub-replay-key"},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["version"] == second.json()["version"]
    # 重放没有再次发布产生第二笔业务效果。
    published = [
        d for d in client.get(f"{API}/tickets/{submitted['ticket_id']}/drafts").json()
        if d["status"] == "PUBLISHED"
    ]
    assert len(published) == 1


# --- 6：角色与可见性 ----------------------------------------------------------


def test_customer_cannot_edit_or_publish_draft(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    login: object,
) -> None:
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-role-key-1")
    draft_id = _active_draft_id(client, submitted["ticket_id"])

    edit = client.patch(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}",
        json={"content": "客户想改"},
        headers={"X-CSRF-Token": customer_csrf, "Idempotency-Key": "cust-edit"},
    )
    publish = client.post(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}/publish",
        headers={"X-CSRF-Token": customer_csrf, "Idempotency-Key": "cust-pub"},
    )
    assert edit.status_code == 403 and edit.json()["code"] == "forbidden"
    assert publish.status_code == 403 and publish.json()["code"] == "forbidden"


def test_other_agent_can_read_and_edit_draft_in_same_workspace(
    client: TestClient,
    demo_users: None,
    indexed_knowledge: None,
    create_user: object,
    login: object,
) -> None:
    """另一名坐席能读取工单草稿（工作区可见），且同为坐席可编辑。

    只有普通客户被拒（见 ``test_customer_cannot_edit_or_publish_draft``）。
    """
    customer_csrf = login("customer@example.com")
    submitted = _run_happy_path(client, customer_csrf, "draft-other-staff-1")
    drafts = client.get(f"{API}/tickets/{submitted['ticket_id']}/drafts")
    assert drafts.status_code == 200 and len(drafts.json()) == 1

    create_user("agent2@example.com", Role.AGENT)
    other_csrf = login("agent2@example.com")
    draft_id = _active_draft_id(client, submitted["ticket_id"])
    edit = client.patch(
        f"{API}/tickets/{submitted['ticket_id']}/drafts/{draft_id}",
        json={"content": "同事来改"},
        headers={"X-CSRF-Token": other_csrf, "Idempotency-Key": "other-edit"},
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["author"] == "human"
