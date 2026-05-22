# Yara backlog

Idea buffer. Items here are **not yet promoted to a GitHub Issue** — once we pick one up, create an Issue (`gh issue create`) and move the line to the `## Migrated to Issues` section with the Issue link.

Active work lives in GitHub Issues. Use `gh issue list` to see what's open.

## Format

Every item starts with two markers in bold:

```
- [ ] **[Priority] [YYYY-MM-DD]** Short description...
```

- **Priority** is one of:
  - `Now` — the next 1–2 PRs we expect to ship
  - `Next` — in view for the near term, not yet started
  - `Later` — valuable but not soon; revisit when the surrounding context matures
- **Date** is the day the item was added or last meaningfully re-considered (ISO `YYYY-MM-DD`). Lets us spot stale ideas during refinement.

## Bugs / edge cases

- [ ] **[Next] [2026-05-22]** Race condition in `get_or_create_user_by_phone_number`: two near-simultaneous webhooks for a brand-new phone number may both attempt to insert, causing an `IntegrityError` on the unique `phone_number` constraint. Fix: `ON CONFLICT DO NOTHING` or try/except + re-fetch.

## Features

- [ ] **[Next] [2026-05-22]** When a user sends a PDF or photo, download the file from `MediaUrl0`, store it under `storage/uploads/<user_id>/`, and persist the path via `media_storage_path` on the message row.
- [ ] **[Next] [2026-05-22]** When a user sends a document, extract its text with `pypdf` and store it on the `Document` row.
- [ ] **[Next] [2026-05-22]** Bring back the intake workflow (LangGraph): ask about situation, language preference, confirm municipality. Persist state in `workflow_states`. Required by the router architecture (see below).
- [ ] **[Later] [2026-05-22]** DigiD prerequisite subflow — deterministic routing for users who don't have DigiD yet.
- [ ] **[Later] [2026-05-22]** Action creation + reminder scheduling (follow-ups over time).
- [ ] **[Later] [2026-05-22]** Trusted public-service source indexing (official Dutch government sources).

## Router architecture (to refine further)

The router is not the LLM-that-replies — it is a **dispatcher** that inspects user and workflow state and chooses which specialist node handles the message. Mix of deterministic checks (DB queries) and LLM-based decisions where human nuance is needed.

Sub-items to refine before implementation:

- [ ] **[Next] [2026-05-22]** New-vs-existing user check — define "new" precisely. Working hypothesis: no `workflow_states` row with `workflow_type="intake"` and `completed_at IS NOT NULL` → still new → auto-route to intake.
- [ ] **[Next] [2026-05-22]** Active workflow lookup — query `workflow_states WHERE user_id = X AND completed_at IS NULL`. If present, the router knows there is a flow in progress.
- [ ] **[Next] [2026-05-22]** Continue-or-switch dialogue — when an active flow exists and the user sends something that doesn't obviously belong to it, decide whether to interrupt the flow, ask the user, or carry on. Likely small LLM-based classify step.
- [ ] **[Next] [2026-05-22]** Intent classifier for free chat — when intake is done and no active flow exists, classify the message into a coarse intent (document, question, urgent, smalltalk, …) and branch.
- [ ] **[Later] [2026-05-22]** Free-chat / general-question specialist node — what handles messages that don't fit a named flow.
- [ ] **[Now] [2026-05-22]** Actively use `WorkflowState`: every specialist node persists its `workflow_type`, `current_step`, and `state_json` so the router can read them on the next turn.

## Security / hardening

- [ ] **[Next] [2026-05-22]** Validate the Twilio request signature on `/webhooks/twilio/whatsapp` — the endpoint currently accepts any incoming POST.
- [ ] **[Later] [2026-05-22]** File retention policy for `storage/uploads/` (max retention period, periodic cleanup).
- [ ] **[Later] [2026-05-22]** Rotate credentials in `.env` before any broader use; double-check `.env` stays in `.gitignore`.

## Tech debt

- [ ] **[Later] [2026-05-22]** `datetime.utcnow()` in [conversation_service.py:32](app/services/conversation_service.py#L32) is deprecated in Python 3.12; replace with `datetime.now(UTC)`.

## Observability / tooling (to analyse)

- [ ] **[Later] [2026-05-22]** **Evaluate LangSmith vs Langfuse and choose** — both provide LLM tracing: per-call input/output, latency, tokens, cost, graph traces, prompt versioning, datasets for evals. Decision points:
  - **LangSmith**: closed-source SaaS by LangChain. Zero-config integration (env vars). Best graph visualisation for LangGraph. Data leaves our infra.
  - **Langfuse**: open-source, self-hostable (Docker). Vendor-neutral (works with any LLM lib). Self-host = better fit for sensitive user data (newcomers, possibly BSN/DigiD context).
  - **Pre-decision action**: until we choose, attach metadata to every LLM call (`run_name`, `metadata={"conversation_id": ..., "user_id": ..., "source_node": ...}`). Both tools use that for filtering/grouping — essentially free now, saves work later.
  - **Do not yet**: hard-code vendor-specific callbacks. Keep LLM invocations on the standard LangChain interface so we can wire either tool in via config.
- [ ] **[Later] [2026-05-22]** Set up a GitHub Project for visual work tracking. Trade-off: nice once we have 5+ active Issues or contributors; overkill for the current solo / single-Issue throughput. Reconsider when those conditions change.

## Follow-up on the LangGraph router

- [ ] **[Later] [2026-05-22]** Token limit / history truncation: today we send the recent history as-is. Smarter context strategy: summarisation, sliding window, semantic retrieval.
- [ ] **[Next] [2026-05-22]** Support media messages in the router: download PDFs/photos from `MediaUrl0`, store them under `storage/uploads/`, attach via `media_storage_path`. Extract text for PDFs (pypdf).
- [ ] **[Later] [2026-05-22]** Debug endpoint `GET /debug/conversation/{phone_number}` for a quick readable dump of a conversation (alternative to opening a DB GUI).

## Product / architecture documentation

- [ ] **[Later] [2026-05-22]** Write higher-level product and architecture documents (separate, deliberate effort, not a 5-minute job): `project-brief-v1.md`, `mvp-scope-v1.md`, `technical-architecture-v1.md`, `data-model-v1.md`, `user-stories-v1.md`, `implementation-plan-v1.md`. Decide first where they live (one level above the repo, or inside `docs/product/`), then link them from the README.

## Migrated to Issues

- [System prompt + error-handling fallback](https://github.com/pfdesignlabs/yara/issues/4) — #4
- [Remove tracked `__pycache__/*.pyc` files](https://github.com/pfdesignlabs/yara/issues/2) — #2

## Done

- [x] Contextual LLM reply (GPT-4o) via LangGraph router instead of static reply. Conversation history loaded from Postgres ([app/workflows/router.py](app/workflows/router.py)).
- [x] End-to-end test of the router workflow via WhatsApp succeeded.
- [x] `source_node` column on `messages`; outbound messages now record which workflow node produced them. LLM invocations attach `run_name` and `metadata` for future LangSmith/Langfuse integration.
