# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once a first release is cut.

## [Unreleased]

### Added

- Reminder-reply detection (Issue #14 Phase C). When the user replies after the cron dispatcher fired a reminder, doc_helper sees that context and can mark the linked action as done in the same turn.
  - New service helper `find_reminder_user_is_replying_to(session, conversation_id=...)` in `app/services/reminder_service.py`. Strict detection: returns a `Reminder` only when the most-recent outbound message preceding the most-recent inbound was sent by `reminder_dispatcher` within `REMINDER_REPLY_WINDOW=48h`. Any interleaving doc_helper reply or older inbound disqualifies the match.
  - `RouterState` carries a new `replying_to_reminder: dict | None` field. `run_router` populates it via `_reminder_reply_snapshot`, which embeds reminder id + body + sent_at and the linked action id/description/status when `target_type='action'`.
  - `document_helper_node` threads the snapshot into the instruction via a `_reminder_reply_brief` block (PDF + vision paths both). Prompt updated with the reminder-reply behaviour: acknowledge the reminder in one sentence, ask whether the action succeeded, and call `mark_action_done` directly when the user already confirms in the same message.
- `scratch14_test.py` runner — 7 scenarios: happy-path detection, >48h age cutoff, doc_helper outbound after reminder disqualifies, no-inbound case, snapshot builder with linked action, snapshot None case, and a full doc_helper integration with mocked LLM that emits `mark_action_done` from the reminder-reply context. All passing.

- Tool-enabled `document_helper_node` (Issue #14 Phase B). The node now `bind_tools(...)`s `mark_action_done`, `create_reminder`, and `draft_mail` (declared in `prompts.yaml::nodes.document_helper_node.tools`) and runs a manual tool-execution loop inside the node:
  - `_inject_runtime_args` fills the `InjectedToolArg` slots (`session`/`user_id`/`conversation_id`) only for tools whose Pydantic args_schema actually declares them — `draft_mail` is left untouched.
  - `_execute_tool_calls` invokes each tool requested by the LLM and returns a list of `ToolMessage`s. Per-tool errors are caught and surfaced as `ToolMessage(content="Tool error: ...", status="error")` so the LLM can react in its next turn instead of crashing the conversation.
  - `_invoke_with_tool_loop` re-invokes the LLM with the new tool messages, bounded by `_MAX_TOOL_ITERATIONS = 3`.
  Prompt updated to describe per-tool trigger policy: `mark_action_done` + `create_reminder` may be called directly when context is clear (MVP behaviour — backlog item tracks the switch to full confirmation for production), `draft_mail` only after explicit user confirmation. Hard rule: max one proposal per turn.
- `scratch13_test.py` runner — 7 deterministic scenarios with a mocked LLM and real DB: schema-aware injection, happy-path tool execution, `ValueError` → error `ToolMessage`, unknown-tool name, loop returns first response when no tool_calls, one-round loop (2 LLM calls + DB write), and bounded retry when the LLM keeps emitting tool_calls. All passing.

### Changed

- Split `app/workflows/intake.py` into two files to match the per-node-type convention already used for `document_helper.py` + `doc_metadata.py`: `intake.py` now holds only the client-facing `intake_node`, and `intake_extractor.py` holds the internal `state_extractor_node` + `ExtractedState` schema. Pure refactor, no behaviour change.

### Added

- Document metadata extractor (Issue #14 Phase A). New internal node `extract_doc_metadata_node` in `app/workflows/doc_metadata.py` that runs once per new Document via `with_structured_output(DocMetadata)`. Extracts `document_type` (free Dutch label), `urgency` (`today`/`this_week`/`this_month`/`no_deadline`), `deadline_date` (ISO), and a list of `ActionDraft` (description, action_type, urgency, deadline_date). Each extracted action is persisted via `create_action(source_type='document_helper', source_id=<document.id>, ...)` so downstream turns can read them from the DB instead of re-extracting. Idempotent — `extract_and_persist_doc_metadata` returns existing rows when actions for the document already exist.
- `document_helper_node` now calls the extractor at entry and surfaces the persisted actions to the explanation LLM via an `---ACTIES---` block in the instruction. Prompt updated so the speaker names the top 1-2 actions (with urgency + deadline) in the user's preferred language. The vision and PDF paths share the new `_actions_brief` helper.
- `RouterState` now carries `session: Session` and `conversation_id: str` so specialist nodes can write to the DB. Both are populated in `run_router`.
- `scratch12_test.py` runner — 5 scenarios with real DB and real LLM call: structured extract returns valid `DocMetadata`, persistence writes correct rows, second call is idempotent (no new rows), empty `documents` is a no-op, and a PDF with no extracted text returns `[]` without crashing.
- APScheduler bootstrap + reminder dispatcher (Issue #13 Phase 3 — closes #13). `app/scheduler/cron.py` boots a single in-app `BackgroundScheduler` with a `SQLAlchemyJobStore` pointed at the Postgres database (restart-safe). One interval job `reminder_dispatcher` ticks every minute and calls `dispatch_due_reminders` in `app/scheduler/reminder_dispatcher.py`. The dispatcher: queries `list_due_reminders`, looks up the user's `phone_number`, sends the `body_template` verbatim over Twilio, persists an outbound `messages` row with `source_node="reminder_dispatcher"`, and flips the reminder to `status='sent'`. Per-reminder errors are logged via `logger.exception` and do not crash the tick — the next interval retries any rows still `scheduled`. Reminders with `conversation_id IS NULL` are logged + skipped (BACKLOG item tracks stand-alone reminder support). Scheduler start/stop is wired via FastAPI's modern `lifespan` context manager in `app/main.py`.
- `apscheduler==3.11.2` dependency in `requirements.txt`.
- `scratch11_test.py` runner — 5 scenarios against the live database with Twilio mocked: happy path, future reminder not picked up, conversation-less reminder skipped, Twilio failure leaves reminder scheduled (no outbound row), and batch dispatch in a single tick. All passing.
- `draft_mail` LLM tool (Issue #13 Phase 2.5) at `app/tools/mail_tools.py::draft_mail`. LLM-visible args: `to_email`, `subject`, `body`. No DB and no injected runtime args — pure utility. Builds an RFC 6068 `mailto:` URL with `urllib.parse.quote(safe="")` so spaces become `%20` (not `+`) and newlines become `%0A`. Validates that `to_email` contains `@`, otherwise raises `ValueError`. Docstring instructs the LLM to write the email in Dutch only when the user is already chatting in Dutch, and bilingual (user language + `---` + Dutch translation) otherwise. Closes Phase 2 of Issue #13.
- `cancel_reminder` LLM tool (Issue #13 Phase 2.4) at `app/tools/reminder_tools.py::cancel_reminder`. LLM-visible arg: `reminder_id`. Session injected. Wraps `cancel_reminder` service; sets `status='cancelled'` and stamps `cancelled_at`. Use case: user signals an action is already done so the proactive follow-up is no longer needed.
- `create_reminder` LLM tool (Issue #13 Phase 2.3) at `app/tools/reminder_tools.py`. LLM-visible args: `target_type`, `target_id`, `when_iso` (ISO 8601 string, parsed to datetime), `body_template`. Runtime args (`session`, `user_id`, `conversation_id`) injected via `InjectedToolArg`. Accepts both bare dates ("2026-06-15") and full timestamps ("2026-06-15T14:00:00Z").
- `app/tools/_helpers.py` with the shared `parse_iso(value)` helper. `action_tools.py` refactored to import from it (previously had `_parse_iso` private to that module).
- `create_action` LLM tool (Issue #13 Phase 2.2) at `app/tools/action_tools.py::create_action`. LLM-visible args: `description`, `source_type`, `source_id`, `action_type`, `urgency`, `deadline_date` (ISO 8601 string, parsed to datetime). Runtime args (`session`, `user_id`, `conversation_id`) are injected via LangChain `InjectedToolArg` so they never appear in the LLM-facing tool schema. `mark_action_done` refactored to the same `InjectedToolArg` pattern — the BACKLOG item tracking that refactor has been migrated into this commit and removed.
- `app/tools/` package with the first LangChain `@tool` wrapper (Issue #13 Phase 2.1). `app/tools/action_tools.py::mark_action_done(action_id)` is exposed to LLMs and sets the action's `status='done'` + stamps `completed_at`.
- `TOOL_REGISTRY` dict + `tools_for_node(node_name)` helper in `app/tools/__init__.py`. Reads `nodes.<name>.tools` from `prompts.yaml` and resolves each entry to a registered tool, raising at startup on unknown names so YAML typos fail loud rather than at LLM-call time.
- `scratch6_test.py` runner: 5 scenarios (tool metadata, happy-path DB side-effect, ValueError on missing action, registry lookup, `tools_for_node` strictness). All passing.
- Polymorphic `actions` and `reminders` tables (Issue #13 Phase 1 — foundation for any feature that needs action-tracking or proactive reminders, reusable across specialists via `(source_type, source_id)` and `(target_type, target_id)` references). Indexes are optimised for "open actions per user" and "due reminders" queries (partial indexes that only cover the active rows).
- ORM models `app/models/action.py` (`Action`) and `app/models/reminder.py` (`Reminder`), exported from `app/models/__init__.py`.
- Service layer (pure CRUD, no LLM coupling):
  - `app/services/action_service.py`: `create_action`, `mark_action_status` (validates status + sets `completed_at` on `done`), `list_pending_actions_for_user`, `list_actions_for_source`.
  - `app/services/reminder_service.py`: `create_reminder`, `list_due_reminders` (status=`scheduled` AND `scheduled_for <= now`), `mark_reminder_sent`, `cancel_reminder`.
- Alembic migration `b66090267d79_add_actions_and_reminders_tables.py` with CHECK constraints on `status` and partial indexes for cron-friendly lookups. Downgrade tested and reversible.
- `scratch5_test.py` runner — 11 CRUD scenarios against the live database covering both services. All passing.
- `document_helper_node` specialist (Issue #11). After intake completes with `matched_workflow="document_helper"`, the router dispatches here. Lives in `app/workflows/document_helper.py` and `app/prompts/prompts.yaml` (`node_type: client`).
  - For PDFs: reads `documents.extracted_text` and asks the LLM to explain in the user's `preferred_language` at B1 level, with kernpunt + deadlines/bedragen + concrete vervolgstap. Truncates at 24 000 chars and lets the LLM know when truncation kicked in.
  - For images: gpt-4o vision via a multimodal `HumanMessage` (text + base64 `image_url`). Multi-image support — consecutive image uploads in the same conversation are treated as pages of one document and sent together (capped at 10).
  - Follow-up turns drop the verbose "explain everything" framing and instead instruct the model to answer the specific user question in 1-3 sentences.
  - No document yet → polite one-line ask, with a hint that PDFs (or multiple photos in a row) work for multi-page letters.
- `app/services/attachment_service.py`: downloads Twilio media with HTTP Basic auth to `storage/uploads/<user_id>/<external_message_id><ext>`, creates the `documents` row, runs `pypdf` text extraction for PDFs, and exposes `get_recent_documents_for_doc_helper` (latest PDF or batch of consecutive images).
- `app/workflows/_llm.py`: `llm_for_node(name)` factory that reads `model` and `temperature` from `get_node_config(name)` and caches `ChatOpenAI` instances per `(model, temperature)` tuple.
- `langcodes[data]==3.5.1` dependency for ISO-639 → Dutch language names in doc_helper instructions.
- `scratch4.py` + `scratch4_test.py` runner for doc_helper (PDF, image, multi-image, multi-language scenarios — 9/9 keyword checks passing on the final iteration).
- E2E webhook test: full intake → handoff → doc_helper vision reply on a real WhatsApp message body, with `source_node="document_helper_node"` tagged correctly on the outbound row.
- Intake workflow + minimal router dispatch (Issue #7). On a user's first inbound message the router creates a `workflow_states` row of `workflow_type="intake"`. Each turn runs through a three-node sub-graph:
  - `router_node` — pure Python dispatcher, reads `workflow_states` and decides whether intake is in progress or done.
  - `state_extractor_node` — `internal` node (`gpt-4o-mini`, `with_structured_output`), runs once per intake turn and fills slots: `information_need`, `preferred_language`, `family_composition`, `country_of_origin`, `residence_status`, `dutch_proficiency`, `matched_workflow`. Opportunistic capture — anything the user volunteers gets recorded without explicit asking.
  - `intake_node` — `client` node (`gpt-4o`), conversational reply with three modes: Mode A (doorvragen) when info is too vague, Mode B (warm document-hand-off) when both sender + subject are known and `matched_workflow="document_helper"`, Mode C (warme wegwijzer) when `matched_workflow="none"` (vraag valt buiten pilot — kort beleefd doorverwijzen). A taalcheck-gate vóór de modes vraagt expliciet om voorkeurstaal wanneer `dutch_proficiency="limited"`.
  - On intake completion (`matched_workflow != null`) the row's `completed_at` is set and `preferred_language` is written back to `users`. Subsequent turns route to `chat_node`.
- `intake_node`, `state_extractor_node`, and `fallbacks.unmatched_workflow` entries in `app/prompts/prompts.yaml`.
- `app/workflows/intake.py` with `ExtractedState` Pydantic schema, `state_extractor_node`, and `intake_node` (shared between production and `scratch3.py`).
- `app/services/workflow_state_service.py` with `get_latest_intake` and `create_intake`.
- `scratch3.py` REPL + `scratch3_test.py` runner for prototyping intake conversation behaviour against the live LLMs (8 scenarios, all passing in the final iteration).
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

- `app/workflows/router.py` graph adds a `document_helper_node` destination. `RouterState` gets a `documents: list[dict]` field; the router computes that snapshot (only when intake is done AND `matched_workflow="document_helper"`) before invoking the graph, so DB access stays out of the graph itself. The three conditional-edge destinations are now `intake_flow` (state_extractor → intake_node), `doc_helper` (document_helper_node), and `chat` (chat_node).
- `intake_node`'s Mode B copy is now a one-sentence warm handoff ("Ik verbind je door naar het documenten-onderdeel") rather than the "specialist function still in development" message — doc_helper exists, the previous wording would be misleading.
- `app/workflows/router.py::_chat_node` and `app/workflows/intake.py` (intake_node + state_extractor_node) use `llm_for_node(...)` from `app/workflows/_llm.py` instead of module-level `ChatOpenAI(...)` instances. Model and temperature now come from `prompts.yaml` per node, with no hard-coded defaults in Python.
- `app/api/routes.py` downloads any inbound Twilio media (`MediaUrl0` + `MediaContentType0`) to `storage/uploads/<user_id>/<sid>.<ext>` and creates a `documents` row tied to the inbound `messages.id`. Failures in the download path are logged but do not crash the webhook.
- `app/workflows/router.py` is now a real dispatcher. `RouterState` extended with `slots`, `user_id`, `intake_done`, and `next`. The graph wires `START → router_node → (state_extractor + intake_node | chat_node) → END`. The single-node `_process` is replaced by `_chat_node`, tagged `source_node="chat_node"`.
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
