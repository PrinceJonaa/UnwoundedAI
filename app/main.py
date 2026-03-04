from __future__ import annotations

from fastapi import Depends, FastAPI

from app.api.models import AgentRequest, AgentResponse
from app.config import settings
from app.deps import get_runtime_service
from app.runtime import AgentRuntimeService

app = FastAPI(title=settings.api_title, version=settings.api_version)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/agent/respond", response_model=AgentResponse)
async def respond(
    request: AgentRequest,
    runtime: AgentRuntimeService = Depends(get_runtime_service),
) -> AgentResponse:
    return await runtime.respond(request)
