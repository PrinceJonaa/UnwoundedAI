# THE UNWOUNDED AI — Runtime Architecture Spec

## 1. Objective
Build a production-grade agent runtime that counters RLHF-style sycophancy by:
1. Explicitly representing uncertainty.
2. Preferring halt/ask/refuse over guessing.
3. Declaring operating mode in every response.
4. Self-evaluating output before user visibility.

## 2. Fixed Technology Stack
1. LangGraph: state machine runtime, cyclic graph control, checkpointer-backed L1/L2.
2. Mem0: durable L3 memory store ("hippocampus"), retrieval + controlled promotion.
3. Braintrust (primary) or LangSmith (adapter): quality vector + trace observability.
4. FastAPI + LiteLLM: API surface and model routing.

## 3. Runtime Modes
- TRUTH_MODE: strict factuality; high confidence threshold; uncertain => HALT/ASK.
- RELATIONAL_MODE: creative/supportive exploration; speculation must be labeled.
- INTEGRATION_MODE: dual-lens output with explicit FACT vs IDEA tagging.

Mode is stored in state and emitted in response header/body metadata on every turn.

## 4. Memory Architecture
### L1 Working Pad (LangGraph state)
Holds active turn data:
- user goal
- active mode
- mode thresholds
- risk class
- retrieval attempts
- candidate draft
- quality vector
- gate decision

### L2 Session Log (LangGraph checkpointer)
Append-only replayable thread state.
- Recommended backend: Postgres checkpointer for production durability.
- Default local mode: in-memory checkpointer.
- Supports time-travel debugging and deterministic replay per session/turn.

### L3 Wisdom Base (Mem0)
Durable user memory with explicit promotion controls:
- memory types: preference, boundary, stable_rule, scar
- NEVER auto-promote raw tool output
- promotion requires:
  - explicit user confirmation, OR
  - repeated verification across turns/sessions with no contradiction
- failed/unsafe reasoning outcomes can be written as "scar" only with high confidence and non-sensitive content policy checks

## 5. Quality & Confidence Vector
Computed in Eval Node before user-visible output:
- internal_consistency: self-consistency of draft and claims
- external_correspondence: grounding from retrieval/evidence
- mode_compliance: adherence to active mode rules
- calibration_signal: confidence calibration (sampling/logprob/surrogate agreement)

Weighted aggregate (default):
- 0.30 * internal_consistency
- 0.35 * external_correspondence
- 0.25 * mode_compliance
- 0.10 * calibration_signal

## 6. Gate Policy (Threshold of Choice)
Possible decisions:
- PASS
- HALT
- REQUIRE_RETRIEVAL
- DOWNGRADE_MODE

### Decision order (deterministic)
1. If mode_compliance below threshold => HALT.
2. If retrieval stagnates or max retries reached without quality improvement => HALT.
3. If evidence insufficient and retrieval attempts remain => REQUIRE_RETRIEVAL.
4. If TRUTH_MODE fails evidence after max retrieval and downgrade allowed and risk not HIGH_STAKES => DOWNGRADE_MODE to INTEGRATION_MODE.
5. If all dimension thresholds + aggregate pass => PASS.
6. Else => HALT.

### High-stakes override
For legal/medical/financial/safety-critical prompts:
- disable mode downgrade
- strict HALT/ASK behavior if confidence/evidence are insufficient

## 7. LangGraph Node Flow
Per user turn:

1. Ingest Node
- accept message + session context
- retrieve L3 candidates from Mem0
- hydrate L1 state

2. Action Node
- determine/confirm mode (user override or classifier policy)
- classify risk
- run retrieval planning

3. Draft Node
- generate hidden candidate response
- extract claim set + evidence links

4. Eval Node
- compute Quality Vector
- record dimension explanations

5. Gate Node (Threshold of Choice)
- PASS => Finalize Node
- REQUIRE_RETRIEVAL => retrieval loop to Draft/Eval
- DOWNGRADE_MODE => switch to INTEGRATION_MODE then re-draft
- HALT => Honest Halt/Ask response path

6. Finalize Node
- emit response with explicit mode header
- format FACT/IDEA sections if INTEGRATION_MODE
- evaluate L3 promotion candidates under policy
- log full trace + vector to Braintrust

## 8. ASCII Graph

START
  |
  v
[INGEST] --> [ACTION] --> [DRAFT] --> [EVAL] --> [GATE]
                                                |   |   |   |
                                                |   |   |   +--> DOWNGRADE_MODE --> [SET MODE=INTEGRATION] --> [DRAFT]
                                                |   |   +------> REQUIRE_RETRIEVAL --> [RETRIEVE] --> [DRAFT]
                                                |   +----------> HALT --> [HONEST_HALT_ASK] --> [FINALIZE]
                                                +--------------> PASS --> [FINALIZE]
                                                                    |
                                                                    v
                                                                   END

## 9. Public API Contract
### Endpoint
POST /v1/agent/respond

### Request JSON
- session_id: string
- user_id: string
- message: string
- requested_mode: TRUTH_MODE | RELATIONAL_MODE | INTEGRATION_MODE | null
- allow_mode_downgrade: boolean (default true)
- metadata: object (optional)

### Response JSON
- mode: TRUTH_MODE | RELATIONAL_MODE | INTEGRATION_MODE
- gate_decision: PASS | HALT | REQUIRE_RETRIEVAL | DOWNGRADE_MODE
- confidence: float [0,1]
- quality_vector: object
- answer: string
- fact_block: string | null
- idea_block: string | null
- citations: list
- asked_clarifying_question: string | null

### User-visible response header (always)
Mode: <MODE> | Gate: <DECISION> | Confidence: <score>

## 10. Operational Rules
- Never emit hidden draft text directly.
- Never suppress uncertainty when confidence is below mode threshold.
- Always prefer: ASK > HALT > GUESS.
- In RELATIONAL_MODE, mark speculative content explicitly.
- In INTEGRATION_MODE, enforce explicit FACT vs IDEA sectioning.

## 11. Testing & Acceptance Criteria
### Functional tests
1. Mode declaration appears in every response.
2. Gate blocks low-confidence drafts from user.
3. Retrieval loop triggers when evidence missing.
4. TRUTH->INTEGRATION downgrade only when allowed and non-high-stakes.
5. High-stakes prompts refuse guessing and do not downgrade.

### Red-team sycophancy tests
1. User pressure: "Just agree with me."
2. Fabricated citation prompt.
3. Confident tone bait with false premise.
4. Contradictory user instructions forcing compliance.
5. "Never say you are unsure" adversarial instruction.

### Acceptance bar
- 100% pass on gating invariants.
- 0 leaked hidden drafts.
- Observable trace + vector logged for every turn.
