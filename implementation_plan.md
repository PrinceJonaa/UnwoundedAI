# Implementation Plan (3 Phases)

## Phase 1: LangGraph Skeleton + Mem0 Integration
### Goal
Stand up the runtime skeleton with deterministic state flow and L3 read/write policy guardrails.

### Scope
1. Create FastAPI service shell and OpenAI-style request/response contract.
2. Add LiteLLM router configuration with primary/fallback models.
3. Implement LangGraph graph with stub nodes:
   - Ingest
   - Action
   - Draft
   - Eval (placeholder)
   - Gate (placeholder)
   - Finalize
4. Wire LangGraph checkpointer (Postgres recommended, in-memory by default for local runs).
5. Integrate Mem0 read path during Ingest.
6. Implement L3 promotion policy service with strict default: no auto-promotion of tool outputs.
7. Add structured response header format for mode declaration.

### Exit Criteria
1. End-to-end request traverses graph and returns response with mode header.
2. L2 checkpoints replay successfully for a session.
3. Mem0 retrieval context is loaded into L1 state.
4. No writes to L3 occur without explicit policy approval path.

### Tests
1. API contract tests for request/response schema.
2. Graph traversal test for happy path.
3. Checkpointer replay test.
4. L3 promotion guardrail test (auto-promotion blocked).

## Phase 2: Eval Node + Threshold of Choice Gate
### Goal
Implement anti-sycophancy cognition core: quality scoring + deterministic gate actions.

### Scope
1. Implement Quality Vector calculators:
   - internal_consistency evaluator
   - external_correspondence evaluator (objective claim-to-evidence check)
   - mode_compliance evaluator
   - calibration_signal evaluator
2. Implement gate decision engine with explicit decision order and thresholds.
3. Add retrieval loop policy with max attempts and stagnation detection.
4. Add TRUTH->INTEGRATION downgrade logic with high-stakes prohibition.
5. Implement HALT/ASK response templates prioritizing honesty over guessing.
6. Enforce INTEGRATION FACT/IDEA dual-section formatting.
7. Add uncertainty markup rules in RELATIONAL mode.

### Exit Criteria
1. PASS/HALT/REQUIRE_RETRIEVAL/DOWNGRADE_MODE all reachable and deterministic.
2. Low-evidence prompts never bypass Gate in TRUTH_MODE.
3. High-stakes prompts refuse downgrade.
4. All user-visible outputs include mode + gate + confidence metadata.

### Tests
1. Unit tests for threshold comparison and gate routing matrix.
2. Property tests for gate invariants (no PASS without quality vector).
3. Integration tests for retrieval loop and fallback behavior.
4. Golden tests for response formatting per mode.

## Phase 3: Braintrust Observability + Sycophancy Red-Team Suite
### Goal
Make runtime measurable and robust under adversarial prompting.

### Scope
1. Instrument each LangGraph node with trace spans.
2. Log Quality Vector, gate decision, mode transitions, and retrieval attempts to Braintrust.
3. Add LangSmith-compatible telemetry adapter interface (optional backend swap).
4. Build red-team prompt suite focused on sycophancy/hallucination pressure.
5. Define regression scorecards:
   - hallucination intercept rate
   - unjustified confidence rate
   - mode compliance rate
   - honest halt rate under insufficient evidence
6. Add CI evaluation run with failure thresholds for merge blocking.

### Exit Criteria
1. 100% turns produce trace + vector logs.
2. Red-team suite runs in CI with versioned reports.
3. Merge is blocked when anti-sycophancy quality gates regress.
4. Operational dashboard can filter by session, mode, gate decision, and failure cluster.

### Tests
1. Telemetry completeness tests.
2. Prompt-based eval tests for adversarial cases.
3. Regression tests comparing baseline vs candidate runtime.
4. Load test to confirm instrumentation does not break latency SLO target.

## Operational Readiness Definition
1. No hidden draft leakage.
2. No high-stakes speculative answers when evidence is insufficient.
3. Deterministic gate behavior across replays.
4. L3 memory writes remain policy-compliant and auditable.
