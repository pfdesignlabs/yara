# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once a first release is cut.

## [Unreleased]

### Added

- `APP_ENV` and `LOG_LEVEL` env vars wired in `app/main.py`. `LOG_LEVEL` drives `logging.basicConfig` at boot. `APP_ENV` (a) toggles `/docs`, `/redoc`, and `/openapi.json` (enabled only when `APP_ENV=development`, hidden elsewhere) and (b) gates a fail-fast secret check: in non-development environments boot raises `RuntimeError` if `OPENAI_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, or `TWILIO_WHATSAPP_NUMBER` is empty. Each deploy is expected to ship its own `.env` with the right values for that environment.
- Yara client persona prepended as a `SystemMessage` on every LLM call in `app/workflows/router.py::_process`. The persona aligns with the project brief: B1-level Dutch, concrete next-step at the end of every reply, hedged answers when uncertain, non-preachy hand-off for professional advice (legal/medical/financial), and language switching that follows the user's most recent message. Lives in `app/prompts/prompts.yaml` under `node_types.client.base_persona` and is loaded via `get_node_prompt("chat_node")`.
- Per-node configuration scaffolding in `app/prompts/prompts.yaml`: `node_types.<type>` holds defaults (model, temperature, base_persona) and `nodes.<name>` holds per-node config (`node_type`, optional `node_task`, optional `tools` list, optional model/temperature overrides). Loader exposes `get`, `get_node_prompt`, and `get_node_config`. Today only `chat_node` exists; the schema anticipates intake/document_helper/router/etc.
- Error-handling fallback in `run_router`: a broad `try/except` around history loading and `agent.invoke` logs the exception with stack trace via stdlib `logging` and returns the static `fallbacks.llm_error` message with `source_node="error_fallback"` instead of crashing the webhook.
- LangGraph router (`app/workflows/router.py`) that replaces the static reply with a GPT-4o response. Conversation history is loaded from Postgres per `conversation_id`.
- `source_node` column on the `messages` table so every outbound message records which workflow node produced it. Tagged on the AI message via `additional_kwargs` and persisted by `create_outbound_message`.
- Observability scaffolding: `agent.invoke` now receives `run_name` and a `metadata` block (`conversation_id`, `user_id`). Ready to pick up by LangSmith or Langfuse once chosen.
- `app/prompts/` module with a YAML-backed loader (`app/prompts/__init__.py`) and `app/prompts/prompts.yaml` containing the Yara client persona and the LLM-error fallback message. Loader exposes a `get("dotted.key")` API.
- `pyyaml==6.0.3` as an explicit dependency in `requirements.txt`.
- `requirements-dev.txt` with `ruff==0.15.14` and `pre-commit==4.0.1` for linting, formatting, and git hooks.
- `pyproject.toml` with the ruff configuration (rules: E, F, I, UP, B, SIM; line length 100; FastAPI `Depends` excluded from B008).
- `.pre-commit-config.yaml` with three hooks: ruff (lint + format), `conventional-pre-commit` (commit message validation), and `gitleaks` (secret scan).
- `.github/workflows/ci.yaml` with three CI jobs: ruff check + format, gitleaks secret scan, and a CHANGELOG check that fails any PR with `feat:` or `fix:` commits that does not modify `CHANGELOG.md`.
- AGPL-3.0 `LICENSE`.
- Coding process documentation: `CLAUDE.md`, `docs/process/git-workflow.md`, `docs/process/spec-template.md`, `docs/process/story-template.md`.

### Changed

- `app/core/config.py::Settings` only declares fields the application actually reads: `app_env`, `log_level`, `database_url`, `openai_api_key`, `twilio_account_sid`, `twilio_auth_token`, `twilio_whatsapp_number`.
- `docker-compose.yml` reads Postgres credentials from `.env` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`) instead of hardcoding them in the `db` service environment block. `.env` is now the single source of truth for DB credentials.
- `.env` cleaned up: only variables that are read by the application or docker-compose remain.
- `app/api/routes.py` calls `run_router` instead of returning a hard-coded `STATIC_REPLY`. Outbound messages now persist `source_node`.
- `create_outbound_message` accepts an optional `source_node` parameter.

### Removed

- Unread `Settings` fields: `app_port`, `whatsapp_provider`, `meta_access_token`, `meta_phone_number_id`, `base_url`, `uploads_dir`, `default_language`, `default_municipality`. They were leftovers from earlier scaffolding and silently misled anyone reading the config. Each one comes back the day a feature actually needs it.
- Static reply constant in `app/api/routes.py`.
- Empty `data/` directory and stale references to it in the README.
- Tracked `__pycache__/*.pyc` files in `app/api/`, `app/models/`, and `app/services/`. They were leftovers from before `.gitignore` covered them; some referenced modules that no longer exist (`digid_blocker_service`, `digid_reply_service`, `guided_journey_service`, `knowledge_service`, `reply_service`, `workflow_service`).
