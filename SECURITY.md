# Security & Distortion Policy

In Unwounded AI, security includes both traditional software vulnerabilities and **systemic distortions** that bypass coherence gates.

## Supported Versions

Security support is provided for:
- `main`
- latest tagged release

## What Counts as a Vulnerability

Please report any of the following:

1. **Sycophancy Bypass**
A prompt sequence that forces confident agreement with false premises by bypassing evidence or gate logic.

2. **L3 Memory Poisoning**
A method that promotes long-term memory without required confirmation or verification safeguards.

3. **Credential or Secret Exposure**
Leaks of keys/tokens/secrets in logs, traces, CLI output, or runtime responses.

4. **Sandbox / Isolation Escape**
Unexpected access to network, host env vars, or restricted resources in constrained execution contexts.

5. **Gate Integrity Regression**
Any path that weakens `HALT`/`ASK` behavior for high-risk or evidence-poor prompts.

## How to Report

Do not open public issues for vulnerabilities.

Use one of the following private channels:
- Email: `jonathanbonner.professional@gmail.com`
- GitHub private vulnerability reporting (security advisory flow)

Include:
- reproduction steps (or exact prompt sequence)
- expected vs actual behavior
- impact level
- logs/screenshots if safe to share

## Response Targets

- Initial maintainer response target: within 72 hours
- Triage includes severity, exploitability, and mitigation plan
- Fix and disclosure timing are coordinated privately before public disclosure
