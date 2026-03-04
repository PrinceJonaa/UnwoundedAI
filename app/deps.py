from __future__ import annotations

from functools import lru_cache

from app.config import RuntimeSettings, settings
from app.graph.nodes import RuntimeNodes
from app.graph.runtime import UnwoundedRuntime
from app.runtime import AgentRuntimeService
from app.services.llm import LiteLLMService
from app.services.memory import InMemoryMemoryService, Mem0MemoryService
from app.services.observability import (
    BraintrustObservabilityService,
    LangSmithObservabilityAdapter,
    NullObservabilityService,
)
from app.services.promotion import L3PromotionPolicy
from app.services.retrieval import RetrievalService
from app.services.search import DuckDuckGoSearchClient, NullSearchClient, TavilySearchClient


@lru_cache(maxsize=1)
def get_settings() -> RuntimeSettings:
    return settings


@lru_cache(maxsize=1)
def get_runtime_service() -> AgentRuntimeService:
    cfg = get_settings()

    memory_service = (
        Mem0MemoryService(api_key=cfg.mem0_api_key) if cfg.mem0_enabled else InMemoryMemoryService()
    )

    if cfg.search_provider == "duckduckgo":
        search_client = DuckDuckGoSearchClient()
    elif cfg.search_provider == "tavily":
        search_client = TavilySearchClient(api_key=cfg.tavily_api_key)
    else:
        search_client = NullSearchClient()

    retrieval_service = RetrievalService(
        memory_service=memory_service,
        search_client=search_client,
        search_max_results=cfg.search_max_results,
        search_timeout_seconds=cfg.search_timeout_seconds,
    )

    if cfg.braintrust_enabled:
        observability = BraintrustObservabilityService(
            project=cfg.braintrust_project,
            api_key=cfg.braintrust_api_key,
        )
    elif cfg.langsmith_enabled:
        observability = LangSmithObservabilityAdapter(project=cfg.langsmith_project)
    else:
        observability = NullObservabilityService()

    llm_service = LiteLLMService(model=cfg.litellm_model, temperature=cfg.litellm_temperature)
    promotion_policy = L3PromotionPolicy()

    nodes = RuntimeNodes(
        llm_service=llm_service,
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        observability_service=observability,
        promotion_policy=promotion_policy,
    )

    runtime = UnwoundedRuntime(nodes=nodes, database_url=cfg.database_url)

    return AgentRuntimeService(runtime=runtime, max_retrieval_attempts=cfg.max_retrieval_attempts)
