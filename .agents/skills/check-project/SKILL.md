---
name: check-project
description: Run the required Korean literature MCP checks after code, configuration, or documentation changes, and report external verification separately.
---

# Check project

From the repository root, install locked dependencies with `uv sync --frozen`
and `npm ci --ignore-scripts` when the environments are not ready.

Run `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy src`, `uv run pytest`, and `npm run lint:md`.
Fix failures and repeat affected checks after the last change.

Tests must use synthetic text or reviewed reusable sources. Never persist a
teacher's passage, draft, or credentials in fixtures, caches, or logs.
Unit tests do not call live institutional APIs. Report real API, Claude
connection, container, and deployment checks separately; do not imply that
passing local tests proves these work.

Report commands and outcomes, remaining review findings, and missing external
inputs. Do not commit, push, or deploy just because checks passed.
