# Unwounded AI Runtime Handoff

## Quick Start
1. Create and activate a virtual environment:
```bash
python3 -m venv .venv
. .venv/bin/activate
```
2. Install dependencies:
```bash
pip install -e '.[dev]'
```
3. Configure environment:
```bash
cp .env.example .env
```
4. Start the interactive CLI:
```bash
python chat.py
```

## CLI Usage
- Send normal prompts directly.
- Force mode at any time:
  - `/mode truth`
  - `/mode relational`
  - `/mode integration`
- Exit with `/quit` or `/exit`.
- The CLI always prints `Mode`, `Gate`, and `Confidence` before the answer.
- On `HALT` or `ASK`, the CLI prompts for additional evidence and resubmits with that evidence attached as a retrieval document.

## Memory Architecture in This Repo
### L1 (Working State)
- Implemented as `L1State` in `/Users/princejona/UnwoundedAI/app/schemas.py`.
- Holds active mode, thresholds, retrieval attempts, draft, quality vector, gate decision, and per-turn metadata.

### L2 (Session Log)
- Managed by LangGraph checkpointer in `/Users/princejona/UnwoundedAI/app/graph/runtime.py`.
- Local default is in-memory `MemorySaver`.
- If `DATABASE_URL` is set, runtime attempts Postgres checkpointer.

### L3 (Long-Term Memory / Mem0)
- `MEM0_ENABLED=false` (default): in-memory memory service only.
- `MEM0_ENABLED=true`: uses `Mem0MemoryService` in `/Users/princejona/UnwoundedAI/app/services/memory.py`.

### L3 Promotion Safeguards
- Promotion policy in `/Users/princejona/UnwoundedAI/app/services/promotion.py`.
- Strict rules:
  - Only `source == user_message` candidates are eligible.
  - `assistant_output` and `tool_output` are rejected for auto-promotion.
  - Allowed auto memory types: `preference`, `boundary`, `stable_rule`.
  - `scar` requires explicit user confirmation and higher confidence.
  - Promotion requires either:
    1. explicit confirmation (`metadata.confirm_memory_promotion=true`), or
    2. repeated verification across turns (`verification_count >= 2` and confidence threshold).
- Candidate extraction and verification ledger are in `/Users/princejona/UnwoundedAI/app/graph/nodes.py`.
- Web search results are retrieval evidence only; they are not promoted to L3 by default.

## How to Enable Mem0 + Tavily
Edit `.env` (from `.env.example`):
```env
MEM0_ENABLED=true
MEM0_API_KEY=your_mem0_key
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_provider_key
```

## Observability (Braintrust / LangSmith)
Observability adapters live in `/Users/princejona/UnwoundedAI/app/services/observability.py`.

### Braintrust
Enable in `.env`:
```env
BRAINTRUST_ENABLED=true
BRAINTRUST_PROJECT=unwounded-ai
BRAINTRUST_API_KEY=your_braintrust_key
```

### LangSmith (fallback adapter)
Enable in `.env`:
```env
LANGSMITH_ENABLED=true
LANGSMITH_PROJECT=unwounded-ai
```

### What gets logged
- Turn start/end
- Quality vector
- Gate decisions
- Retrieval attempts and rationale

## 7D Quality Vector (Verifier Output)
Implemented in `/Users/princejona/UnwoundedAI/app/schemas.py` and computed in `/Users/princejona/UnwoundedAI/app/graph/policies.py`.

Dimensions:
1. `internal_consistency`
2. `external_correspondence`
3. `mode_compliance`
4. `calibration_signal`
5. `citation_fidelity`
6. `claim_coverage`
7. `adversarial_resistance`

Supervisor uses threshold checks to route:
- `PASS`
- `HALT`
- `ASK`
- `REQUIRE_RETRIEVAL`
- `DOWNGRADE_MODE`

## Operational Notes
- Default profile is local-first (`duckduckgo`, in-memory memory, no observability backend).
- If model API keys are missing, drafting falls back deterministically.
- For production hardening, add persistent checkpointer + managed secrets.

## Quick Troubleshooting
- `HALT/ASK` loops: provide a concrete source snippet when prompted.
- No web retrieval results: confirm `SEARCH_PROVIDER` and provider keys.
- No long-term memory persistence: confirm `MEM0_ENABLED=true` and `MEM0_API_KEY`.
