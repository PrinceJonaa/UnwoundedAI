from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import RuntimeNodes
from app.schemas import L1State

logger = logging.getLogger(__name__)


class UnwoundedRuntime:
    def __init__(self, nodes: RuntimeNodes, database_url: str | None = None) -> None:
        self.nodes = nodes
        self.checkpointer = self._build_checkpointer(database_url)
        self.graph = self._build_graph()
        self._turn_counters: dict[str, int] = defaultdict(int)

    def _build_checkpointer(self, database_url: str | None):
        if database_url:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver

                return PostgresSaver.from_conn_string(database_url)
            except Exception as exc:  # pragma: no cover - optional infra
                logger.warning("Postgres checkpointer unavailable, using in-memory: %s", exc)

        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    def _build_graph(self):
        graph = StateGraph(dict)

        graph.add_node("ingest", self.nodes.ingest)
        graph.add_node("action", self.nodes.action)
        graph.add_node("supervisor", self.nodes.supervisor_agent)
        graph.add_node("retriever_agent", self.nodes.retriever_agent)
        graph.add_node("drafter_agent", self.nodes.drafter_agent)
        graph.add_node("verifier_agent", self.nodes.verifier_agent)
        graph.add_node("downgrade_mode", self.nodes.downgrade_mode)
        graph.add_node("honest_halt_ask", self.nodes.honest_halt_ask)
        graph.add_node("finalize", self.nodes.finalize)

        graph.add_edge(START, "ingest")
        graph.add_edge("ingest", "action")
        graph.add_edge("action", "supervisor")

        graph.add_edge("retriever_agent", "supervisor")
        graph.add_edge("drafter_agent", "supervisor")
        graph.add_edge("verifier_agent", "supervisor")
        graph.add_edge("downgrade_mode", "supervisor")

        graph.add_edge("honest_halt_ask", "finalize")
        graph.add_edge("finalize", END)

        graph.add_conditional_edges(
            "supervisor",
            self._route_supervisor,
            {
                "retriever_agent": "retriever_agent",
                "drafter_agent": "drafter_agent",
                "verifier_agent": "verifier_agent",
                "downgrade_mode": "downgrade_mode",
                "honest_halt_ask": "honest_halt_ask",
                "finalize": "finalize",
            },
        )

        return graph.compile(checkpointer=self.checkpointer)

    def _route_supervisor(self, state: dict[str, Any]) -> str:
        next_node = state.get("next_node")
        if isinstance(next_node, str) and next_node:
            return next_node
        return "honest_halt_ask"

    async def next_turn_id(self, session_id: str) -> int:
        config = {"configurable": {"thread_id": session_id}}

        if hasattr(self.graph, "aget_state"):
            try:
                snapshot = await self.graph.aget_state(config)
                if snapshot and getattr(snapshot, "values", None):
                    prior = snapshot.values.get("turn_id")
                    if isinstance(prior, int) and prior >= 1:
                        self._turn_counters[session_id] = prior
                        return prior + 1
            except Exception:  # pragma: no cover - compatibility fallback
                pass

        self._turn_counters[session_id] += 1
        return self._turn_counters[session_id]

    async def invoke_turn(self, state: L1State) -> L1State:
        config = {
            "configurable": {"thread_id": state.session_id},
            "recursion_limit": 48,
        }
        result = await self.graph.ainvoke(state.model_dump(mode="python"), config=config)
        validated = L1State.model_validate(result)
        self._turn_counters[state.session_id] = max(self._turn_counters[state.session_id], validated.turn_id)
        return validated
