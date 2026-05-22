# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once a first release is cut.

## [Unreleased]

### Added

- LangGraph router (`app/workflows/router.py`) that replaces the static reply with a GPT-4o response. Conversation history is loaded from Postgres per `conversation_id`.
- `source_node` column on the `messages` table so every outbound message records which workflow node produced it. Tagged on the AI message via `additional_kwargs` and persisted by `create_outbound_message`.
- Observability scaffolding: `agent.invoke` now receives `run_name` and a `metadata` block (`conversation_id`, `user_id`). Ready to pick up by LangSmith or Langfuse once chosen.
- `requirements-dev.txt` with `ruff==0.15.14` and `pre-commit==4.0.1` for linting, formatting, and git hooks.
- `pyproject.toml` with the ruff configuration (rules: E, F, I, UP, B, SIM; line length 100; FastAPI `Depends` excluded from B008).
- `.pre-commit-config.yaml` with three hooks: ruff (lint + format), `conventional-pre-commit` (commit message validation), and `gitleaks` (secret scan).
- `.github/workflows/ci.yaml` with three CI jobs: ruff check + format, gitleaks secret scan, and a CHANGELOG check that fails any PR with `feat:` or `fix:` commits that does not modify `CHANGELOG.md`.
- AGPL-3.0 `LICENSE`.
- Coding process documentation: `CLAUDE.md`, `docs/process/git-workflow.md`, `docs/process/spec-template.md`, `docs/process/story-template.md`.

### Changed

- `app/api/routes.py` calls `run_router` instead of returning a hard-coded `STATIC_REPLY`. Outbound messages now persist `source_node`.
- `create_outbound_message` accepts an optional `source_node` parameter.

### Removed

- Static reply constant in `app/api/routes.py`.
- Empty `data/` directory and stale references to it in the README.
