import pytest

from app.graph.nodes import RuntimeNodes
from app.graph.policies import threshold_for_mode
from app.graph.runtime import UnwoundedRuntime
from app.schemas import GateDecision, L1State, OperatingMode
from app.services.memory import InMemoryMemoryService
from app.services.observability import NullObservabilityService
from app.services.promotion import L3PromotionPolicy
from app.services.retrieval import RetrievalService
from app.services.search import NullSearchClient


class StaticBadLLM:
    async def draft(self, user_message: str, mode: OperatingMode, evidence_snippets: list[str]):
        class Result:
            text = "This is definitely correct but unsupported."
            confidence_hint = 0.95

        return Result()


@pytest.mark.anyio
async def test_runtime_breaks_retrieval_loops_and_halts_or_asks() -> None:
    memory = InMemoryMemoryService()
    retrieval = RetrievalService(memory, NullSearchClient())
    nodes = RuntimeNodes(
        llm_service=StaticBadLLM(),
        retrieval_service=retrieval,
        memory_service=memory,
        observability_service=NullObservabilityService(),
        promotion_policy=L3PromotionPolicy(),
    )

    runtime = UnwoundedRuntime(nodes=nodes, database_url=None)
    state = L1State(
        session_id="sess-loop",
        user_id="user-1",
        turn_id=1,
        user_message="Provide a verified medical dosage",
        active_mode=OperatingMode.TRUTH_MODE,
        requested_mode=OperatingMode.TRUTH_MODE,
        thresholds=threshold_for_mode(OperatingMode.TRUTH_MODE),
        max_retrieval_attempts=1,
    )

    final_state = await runtime.invoke_turn(state)

    assert final_state.retrieval_attempts <= final_state.max_retrieval_attempts
    assert final_state.final_response is not None
    assert final_state.final_response.gate_decision in {GateDecision.HALT, GateDecision.ASK}
    assert final_state.final_response.gate_decision != GateDecision.PASS
