# PR Review Policy

This policy governs automated pull requests created by repository maintenance agents.

## Required PR Tags

Automated pull requests must include one of these title tags:
- `[AUTO-DOC]` for documentation maintenance
- `[AUTO-REFACTOR]` for single-file refactor maintenance
- `[AUTO-TEST]` for red-team test expansion

## Human Review Requirement

No automated pull request may be merged without human review of potential **Gate Decision** impact.

At minimum, the reviewer must confirm that the change does not degrade or bypass intended `Gate` behavior.

## Approval Separation Rule

Agents are not allowed to approve each other's pull requests.

Automated approvals are prohibited for automated PRs. A human reviewer must provide the required approval before merge.
