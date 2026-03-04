from __future__ import annotations

import asyncio

from app.api.models import AgentRequest
from app.graph.nodes import RuntimeNodes
from app.graph.runtime import UnwoundedRuntime
from app.runtime import AgentRuntimeService
from app.services.llm import LiteLLMService
from app.services.memory import InMemoryMemoryService
from app.services.observability import NullObservabilityService
from app.services.promotion import L3PromotionPolicy
from app.services.retrieval import RetrievalService
from app.services.search import NullSearchClient


async def main() -> None:
    memory = InMemoryMemoryService()
    retrieval = RetrievalService(memory, NullSearchClient())
    llm = LiteLLMService(model="gpt-4o-mini", temperature=0.2)

    nodes = RuntimeNodes(
        llm_service=llm,
        retrieval_service=retrieval,
        memory_service=memory,
        observability_service=NullObservabilityService(),
        promotion_policy=L3PromotionPolicy(),
    )
    runtime = UnwoundedRuntime(nodes=nodes, database_url=None)
    service = AgentRuntimeService(runtime=runtime, max_retrieval_attempts=2)

    request = AgentRequest(
        session_id="demo-session",
        user_id="demo-user",
        message="Verify whether the moon is made of cheese and cite your evidence.",
        requested_mode=None,
        allow_mode_downgrade=True,
        metadata={
            "documents": [
                {
                    "id": "doc-1",
                    "title": "Lunar Geology",
                    "citation": "NASA Lunar Composition",
                    "text": "The moon is made primarily of silicate rock and metal-rich minerals.",
                    "trust_score": 0.95,
                }
            ]
        },
    )

    response = await service.respond(request)
    print(response.header)
    print()
    print(response.answer)
    if response.asked_clarifying_question:
        print()
        print("Clarifying question:", response.asked_clarifying_question)


if __name__ == "__main__":
    asyncio.run(main())
