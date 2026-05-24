# Yara backlog

Idea buffer. Items here are **not yet promoted to a GitHub Issue** — once we pick one up, create an Issue (`gh issue create`) and move the line to the `## Migrated to Issues` section with the Issue link.

Active work lives in GitHub Issues. Use `gh issue list` to see what's open.

## Format

Every item is a single bullet with two bold markers and a `Relevant when` sub-bullet:

```
- [ ] **[Priority] [YYYY-MM-DD]** Short description...
  - **Relevant when:** observable signal(s) that promote this item to actual work.
```

- **Priority** is one of:
  - `Now` — the next 1–2 PRs we expect to ship
  - `Next` — in view for the near term, not yet started
  - `Later` — valuable but not soon; revisit when the surrounding context matures
- **Date** is the day the item was added or last meaningfully re-considered (ISO `YYYY-MM-DD`).
- **Relevant when** is the trigger that turns this item from a thought into a planned PR. Phrase as concrete observable signals (a node shipping, a metric crossed, a user count, a date), not vague intentions. Examples: *"after the document-explainer node ships"*, *"when ≥2 users report behaviour X"*, *"before exposing the bot to non-test users"*.

## Bugs / edge cases

- [ ] **[Next] [2026-05-22]** Race condition in `get_or_create_user_by_phone_number`: two near-simultaneous webhooks for a brand-new phone number may both attempt to insert, causing an `IntegrityError` on the unique `phone_number` constraint. Fix: `ON CONFLICT DO NOTHING` or try/except + re-fetch.
  - **Relevant when:** we observe the actual `IntegrityError` in logs, **or** before testing with more than one concurrent user.

## Features

- [ ] **[Next] [2026-05-22]** When a user sends a PDF or photo, download the file from `MediaUrl0`, store it under `storage/uploads/<user_id>/`, and persist the path via `media_storage_path` on the message row.
  - **Relevant when:** the document-explainer node is being built (this is its file-intake prerequisite).
- [ ] **[Next] [2026-05-22]** When a user sends a document, extract its text with `pypdf` and store it on the `Document` row.
  - **Relevant when:** the document-explainer node is being built (pairs with the file-download item above).
- [ ] **[Next] [2026-05-22]** Bring back the intake workflow (LangGraph): ask about situation, language preference, confirm municipality. Persist state in `workflow_states`. Required by the router architecture (see below).
  - **Relevant when:** starting the router refactor — intake is the first destination the router branches to for new users.
- [ ] **[Later] [2026-05-22]** DigiD prerequisite subflow — deterministic routing for users who don't have DigiD yet.
  - **Relevant when:** trusted public-service source indexing exists (we need accurate DigiD process info), **and** ≥1 logged conversation shows a user blocked by missing DigiD.
- [ ] **[Later] [2026-05-23]** Reminder creation tool — a LangChain `@tool` exposed to every client-facing specialist node (intake, document_helper, free-chat). Takes `text` and `when` arguments, persists to a `reminders` table, returns a confirmation. Modeled as a tool rather than a specialist node so the LLM can create reminders mid-conversation in any flow.
  - **Relevant when:** a user explicitly asks to be reminded about something in ≥2 separate conversations.
- [ ] **[Later] [2026-05-23]** Reminder sender (proactive flow) — scheduled job that picks up due reminders, generates the message text via the LLM (with `personas.client`), and sends it via the Twilio outbound API. Separate code path from the conversational graph (cron-triggered or successor).
  - **Relevant when:** the reminder creation tool ships and ≥1 due reminder exists in the table.
- [ ] **[Later] [2026-05-22]** Trusted public-service source indexing (official Dutch government sources).
  - **Relevant when:** Yara produces a confidently-wrong statement about a government process in ≥1 logged conversation, **or** before any deployment to real users.

## Router architecture (to refine further)

The router is not the LLM-that-replies — it is a **dispatcher** that inspects user and workflow state and chooses which specialist node handles the message. Mix of deterministic checks (DB queries) and LLM-based decisions where human nuance is needed.

Sub-items to refine before implementation:

- [ ] **[Next] [2026-05-22]** New-vs-existing user check — define "new" precisely. Working hypothesis: no `workflow_states` row with `workflow_type="intake"` and `completed_at IS NOT NULL` → still new → auto-route to intake.
  - **Relevant when:** starting the router refactor (this is the first branch).
- [ ] **[Next] [2026-05-22]** Active workflow lookup — query `workflow_states WHERE user_id = X AND completed_at IS NULL`. If present, the router knows there is a flow in progress.
  - **Relevant when:** starting the router refactor.
- [ ] **[Next] [2026-05-22]** Continue-or-switch dialogue — when an active flow exists and the user sends something that doesn't obviously belong to it, decide whether to interrupt the flow, ask the user, or carry on. Likely small LLM-based classify step.
  - **Relevant when:** ≥2 specialist nodes exist (so "switch to what?" has a real answer).
- [ ] **[Next] [2026-05-22]** Intent classifier for free chat — when intake is done and no active flow exists, classify the message into a coarse intent (document, question, urgent, smalltalk, …) and branch.
  - **Relevant when:** intake is done **and** ≥2 specialist nodes exist as routing destinations.
- [ ] **[Later] [2026-05-22]** Free-chat specialist node — handles messages that don't fit a named flow. Acts as the safety net when intake / document_helper / scheduling do not apply. Working name TBD; alternatives to weigh when implementing: `general_chat`, `unstructured_chat`, `fallback_specialist`, `default_chat`.
  - **Relevant when:** logs show users sending messages outside every named flow more than a handful of times (fallback usage signal).
- [ ] **[Now] [2026-05-22]** Actively use `WorkflowState`: every specialist node persists its `workflow_type`, `current_step`, and `state_json` so the router can read them on the next turn.
  - **Relevant when:** starting the router refactor — the router *reads* state, so specialists must *write* it first.

## Security / hardening

- [ ] **[Next] [2026-05-22]** Validate the Twilio request signature on `/webhooks/twilio/whatsapp` — the endpoint currently accepts any incoming POST.
  - **Relevant when:** before the webhook URL is shared with anyone outside the maintainer (hard prerequisite for any non-personal use).
- [ ] **[Later] [2026-05-22]** File retention policy for `storage/uploads/` (max retention period, periodic cleanup).
  - **Relevant when:** the first real user uploads a file, **or** within 30 days of the first stored upload.
- [ ] **[Later] [2026-05-22]** Rotate credentials in `.env` before any broader use; double-check `.env` stays in `.gitignore`.
  - **Relevant when:** before deploying to a real audience, **or** if there is any suspicion of credential exposure.

## Tech debt

- [ ] **[Later] [2026-05-22]** `datetime.utcnow()` in [conversation_service.py:32](app/services/conversation_service.py#L32) is deprecated in Python 3.12; replace with `datetime.now(UTC)`.
  - **Relevant when:** upgrading to Python 3.13+ (where `utcnow` is removed), **or** when CI starts failing on deprecation warnings.
- [ ] **[Later] [2026-05-23]** Harden the `app/prompts/` loader to type-safe access (Pydantic model parsing the YAML on load, or an Enum of keys). Current setup uses a simple `get("dotted.key")` lookup — typos surface only at runtime and there is no IDE autocomplete on prompt keys.
  - **Relevant when:** **any** of the following — the YAML grows beyond ~15 keys, two or more runtime `KeyError`s from typoed prompt keys are observed in dev/prod, a non-author needs to find or modify prompts, cross-prompt invariants emerge (e.g. "every client-facing node must compose with `personas.client`"), **or** A/B testing / per-tenant prompt variations is needed (at that point skip Pydantic and go straight to a DB or LangSmith Hub backing).
- [ ] **[Later] [2026-05-23]** Document the tool architectural pattern alongside specialist nodes — where tools live (likely `app/tools/`), how they are wired into nodes' LLM bindings, how the LLM is briefed about them, and how `personas.tool` (terse, structured-output base for internal classifiers) relates to tools called from inside client-facing nodes. First instance will be the reminder creation tool.
  - **Relevant when:** just before implementing the first tool (currently the reminder creation tool).
- [ ] **[Later] [2026-05-23]** Replace cron with a production-grade scheduler (apscheduler, Celery + Redis, Kubernetes CronJobs, etc.) for the proactive reminder sender. Cron lacks retries, observability, distributed safety, and a dead-letter queue.
  - **Relevant when:** the reminder sender ships **and** more than ~10 active reminders exist, **or** observed missed reminders due to transient failures.
- [ ] **[Later] [2026-05-24]** Wire per-node LLM creation: read `model` and `temperature` from `get_node_config(node_name)` and instantiate a `ChatOpenAI` with those settings instead of the single module-level `llm = ChatOpenAI(model="gpt-4o", ...)`. Cache instances per `(model, temperature)` tuple so we do not allocate a new client per call.
  - **Relevant when:** the first node with a different model lands (the first `internal` node — likely `intent_classifier` or `router_node`).
- [ ] **[Later] [2026-05-24]** Tools infrastructure: an `app/tools/` package holding `@tool`-decorated functions, a name → tool resolver, and wiring in the per-node LLM creation that calls `llm.bind_tools(...)` based on `get_node_config(node_name)["tools"]`. The YAML `tools:` field already exists (empty for `chat_node`); only the code side is missing.
  - **Relevant when:** just before implementing the first concrete tool (likely `create_reminder`) — build the infrastructure together with the tool.

## Observability / tooling (to analyse)

- [ ] **[Later] [2026-05-22]** **Evaluate LangSmith vs Langfuse and choose** — both provide LLM tracing: per-call input/output, latency, tokens, cost, graph traces, prompt versioning, datasets for evals. Decision points:
  - **LangSmith**: closed-source SaaS by LangChain. Zero-config integration (env vars). Best graph visualisation for LangGraph. Data leaves our infra.
  - **Langfuse**: open-source, self-hostable (Docker). Vendor-neutral (works with any LLM lib). Self-host = better fit for sensitive user data (newcomers, possibly BSN/DigiD context).
  - **Pre-decision action**: until we choose, attach metadata to every LLM call (`run_name`, `metadata={"conversation_id": ..., "user_id": ..., "source_node": ...}`). Both tools use that for filtering/grouping — essentially free now, saves work later.
  - **Do not yet**: hard-code vendor-specific callbacks. Keep LLM invocations on the standard LangChain interface so we can wire either tool in via config.
  - **Relevant when:** shipping to ≥3 test users (we need to see what they actually say), **or** when LLM cost exceeds €20/month, **or** when prompt iterations lack comparison data.
- [ ] **[Later] [2026-05-22]** Set up a GitHub Project for visual work tracking. Trade-off: nice once we have 5+ active Issues or contributors; overkill for the current solo / single-Issue throughput.
  - **Relevant when:** active Issues exceed 5 at the same time, **or** a second contributor joins the repo.

## Follow-up on the LangGraph router

- [ ] **[Later] [2026-05-22]** Token limit / history truncation: today we send the recent history as-is. Smarter context strategy: summarisation, sliding window, semantic retrieval.
  - **Relevant when:** average conversation history exceeds ~30 messages, **or** observed truncated/cut-off LLM responses, **or** per-turn cost climbs above €X.
- [ ] **[Next] [2026-05-22]** Support media messages in the router: download PDFs/photos from `MediaUrl0`, store them under `storage/uploads/`, attach via `media_storage_path`. Extract text for PDFs (pypdf).
  - **Relevant when:** the document-explainer node is being built (this is the same work as the two media-related items above, captured here from the router angle).
- [ ] **[Later] [2026-05-22]** Debug endpoint `GET /debug/conversation/{phone_number}` for a quick readable dump of a conversation (alternative to opening a DB GUI).
  - **Relevant when:** debugging via TablePlus / direct DB queries happens more than ~3× per debugging session and starts feeling annoying.

## Product / architecture documentation

- [ ] **[Later] [2026-05-22]** Write higher-level product and architecture documents (separate, deliberate effort, not a 5-minute job): `project-brief-v1.md`, `mvp-scope-v1.md`, `technical-architecture-v1.md`, `data-model-v1.md`, `user-stories-v1.md`, `implementation-plan-v1.md`. Decide first where they live (one level above the repo, or inside `docs/product/`), then link them from the README.
  - **Relevant when:** onboarding a second contributor, **or** when scope decisions become hard to make without a written reference, **or** before a stakeholder review.

## Migrated to Issues

- [System prompt + error-handling fallback](https://github.com/pfdesignlabs/yara/issues/4) — #4
- [Remove tracked `__pycache__/*.pyc` files](https://github.com/pfdesignlabs/yara/issues/2) — #2

## Done

- [x] Contextual LLM reply (GPT-4o) via LangGraph router instead of static reply. Conversation history loaded from Postgres ([app/workflows/router.py](app/workflows/router.py)).
- [x] End-to-end test of the router workflow via WhatsApp succeeded.
- [x] `source_node` column on `messages`; outbound messages now record which workflow node produced them. LLM invocations attach `run_name` and `metadata` for future LangSmith/Langfuse integration.
