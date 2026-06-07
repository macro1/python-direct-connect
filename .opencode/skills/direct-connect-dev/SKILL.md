---
name: direct-connect-dev
description: Use when editing, testing, refactoring, or running static analysis in this repository. Enforces strict zero-ignore type safety, lint compliance, and robust code architectures.
---

# Direct Connect Code Development Guide

* **Code Style:** Strict PEP 8, Ruff formatting, and single-line imports. Avoid code comments unless describing *why* something complex is done.
* **Lint and Type Safety:**
  - Zero ignores: Do not insert inline ignores (e.g., `# type: ignore`, `# noqa`, `# pylint: disable`) or linter overrides without prior user consent.
  - Fallback: If `mypy` or linter blockers are encountered due to upstream constraints, halt the affected path, document the failure, propose 2 type-safe alternatives, and escalate.
* **Test Safety Net:**
  - All runtime additions must be covered by unit tests (target 100% coverage).
  - Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, and the unit tests before declaring any task complete.
