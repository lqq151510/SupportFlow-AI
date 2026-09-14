"""LangGraph checkpoint 的真实 PostgreSQL 契约。"""

from __future__ import annotations

from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from supportflow.agent.infrastructure.checkpoints import (
    checkpoint_config,
    postgres_checkpointer,
)
from supportflow.shared.config import get_settings


class CounterState(TypedDict):
    value: int


def test_checkpoint_uses_run_id_thread_and_reuses_prior_state(migrated: None) -> None:
    run_id = uuid4()

    def increment(state: CounterState) -> CounterState:
        return {"value": state["value"] + 1}

    graph = StateGraph(CounterState)
    graph.add_node("increment", increment)
    graph.add_edge(START, "increment")
    graph.add_edge("increment", END)

    with postgres_checkpointer(get_settings().database_url) as checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
        config = checkpoint_config(run_id)
        assert compiled.invoke({"value": 1}, config) == {"value": 2}
        saved = checkpointer.get(config)

    assert saved is not None
    assert saved["channel_values"]["value"] == 2
