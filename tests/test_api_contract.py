from fastapi.testclient import TestClient

from app.deps import get_runtime_service
from app.main import app
from app.runtime import AgentRuntimeService


class StubRuntimeService(AgentRuntimeService):
    async def respond(self, request):
        from app.api.models import AgentResponse
        from app.schemas import GateDecision, OperatingMode, QualityVector

        return AgentResponse(
            mode=OperatingMode.TRUTH_MODE,
            gate_decision=GateDecision.HALT,
            confidence=0.2,
            quality_vector=QualityVector(
                internal_consistency=0.5,
                external_correspondence=0.1,
                mode_compliance=0.95,
                calibration_signal=0.8,
            ),
            answer="I can't determine that from available evidence.",
            fact_block=None,
            idea_block=None,
            citations=[],
            asked_clarifying_question="Can you provide a source?",
            header="Mode: TRUTH_MODE | Gate: HALT | Confidence: 0.20",
        )


def test_api_contract_shape() -> None:
    app.dependency_overrides[get_runtime_service] = lambda: StubRuntimeService(runtime=None)  # type: ignore[arg-type]
    client = TestClient(app)

    response = client.post(
        "/v1/agent/respond",
        json={
            "session_id": "s1",
            "user_id": "u1",
            "message": "Tell me a fact",
            "allow_mode_downgrade": True,
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "TRUTH_MODE"
    assert body["gate_decision"] == "HALT"
    assert "header" in body
    assert "quality_vector" in body
