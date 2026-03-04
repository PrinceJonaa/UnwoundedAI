# Contributing to Unwounded AI

We welcome contributions from both human developers and automated maintenance agents.

To avoid architectural drift, contributions should follow an **OPWTR loop**:
- **Orient:** understand current behavior and invariants
- **Plan:** define one objective and its verification method
- **Write:** make the smallest defensible change
- **Test:** run the oracle before and after
- **Reflect:** document impact and limits in the PR

## Coherence Contract

Every pull request must satisfy these rules:

1. **Single Objective Scope**
One PR should do one thing. Do not bundle feature work with broad refactors.

2. **Oracle Requirement**
Code changes require a deterministic oracle (tests or reproducible script).
No oracle, no merge.

3. **No Silent Failure Patterns**
Do not swallow errors that should route to explicit `ASK`/`HALT` or visible failure.

4. **Surgical Diff Preference**
Prefer targeted edits over module rewrites. Large rewrites require prior issue-level agreement.

5. **Gate Integrity First**
Changes must not weaken mode thresholds, evidence gating, or anti-sycophancy safeguards without explicit review rationale.

## For Automated Agents

If you are an automated agent (for example Jules roles in `docs/agents/`):

- Prefix PR titles with role tags: `[AUTO-DOC]`, `[AUTO-REFACTOR]`, `[AUTO-TEST]`.
- Do not approve, self-approve, or merge automated PRs.
- Respect file-scope constraints defined in your role prompt.
- Include pre-check and post-check evidence in PR descriptions.

See:
- [docs/agents](./docs/agents)
- [docs/PR_REVIEW_POLICY.md](./docs/PR_REVIEW_POLICY.md)

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run and Test

```bash
uvicorn app.main:app --reload
pytest -q
```

## Submission Steps

1. Branch from `main`.
2. Run baseline tests (`pytest -q`).
3. Make your scoped change.
4. Re-run verification oracle(s).
5. Open PR with:
   - clear objective
   - inputs/outputs changed
   - oracle proof and risk notes
