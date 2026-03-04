from __future__ import annotations

from app.api.models import AgentRequest, AgentResponse
from app.graph.policies import threshold_for_mode
from app.graph.runtime import UnwoundedRuntime
from app.schemas import L1State, OperatingMode


class AgentRuntimeService:
    def __init__(self, runtime: UnwoundedRuntime, max_retrieval_attempts: int = 2) -> None:
        self.runtime = runtime
        self.max_retrieval_attempts = max_retrieval_attempts

    async def respond(self, request: AgentRequest) -> AgentResponse:
        turn_id = await self.runtime.next_turn_id(request.session_id)

        bootstrap_mode = request.requested_mode or OperatingMode.TRUTH_MODE
        state = L1State(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_id=turn_id,
            user_message=request.message,
            metadata=request.metadata,
            requested_mode=request.requested_mode,
            active_mode=bootstrap_mode,
            allow_mode_downgrade=request.allow_mode_downgrade,
            thresholds=threshold_for_mode(bootstrap_mode),
            max_retrieval_attempts=self.max_retrieval_attempts,
        )

        final_state = await self.runtime.invoke_turn(state)
        if final_state.final_response is None:
            raise RuntimeError("Runtime finalized without a response")

        result = final_state.final_response
        return AgentResponse(
            mode=result.mode,
            gate_decision=result.gate_decision,
            confidence=result.confidence,
            quality_vector=final_state.quality_vector,
            answer=result.answer,
            fact_block=result.fact_block,
            idea_block=result.idea_block,
            citations=result.citations,
            asked_clarifying_question=result.clarifying_question,
            header=result.header,
        )
