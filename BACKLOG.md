# Yara backlog

Idea buffer. Items here are **not yet promoted to a GitHub Issue** — once we pick one up, create an Issue (`gh issue create`) and move the line to the `## Migrated to Issues` section with the Issue link.

Active work lives in GitHub Issues. Use `gh issue list` to see what's open.

## Bugs / edge cases

- [ ] Race condition in `get_or_create_user_by_phone_number`: two near-simultaneous webhooks for a brand-new phone number may both attempt to insert, causing an `IntegrityError` on the unique `phone_number` constraint. Fix: `ON CONFLICT DO NOTHING` or try/except + re-fetch.

## Features

- [ ] When a user sends a PDF or photo, download the file from `MediaUrl0`, store it under `storage/uploads/<user_id>/`, and persist the path via `media_storage_path` on the message row.
- [ ] When a user sends a document, extract its text with `pypdf` and store it on the `Document` row.
- [ ] Bring back the intake workflow (LangGraph): ask about situation, language preference, confirm municipality. Persist state in `workflow_states`.
- [ ] DigiD prerequisite subflow — deterministic routing for users who don't have DigiD yet.
- [ ] Action creation + reminder scheduling (follow-ups over time).
- [ ] Trusted public-service source indexing (official Dutch government sources).

## Security / hardening

- [ ] Validate the Twilio request signature on `/webhooks/twilio/whatsapp` — the endpoint currently accepts any incoming POST.
- [ ] File retention policy for `storage/uploads/` (max retention period, periodic cleanup).
- [ ] Rotate credentials in `.env` before any broader use; double-check `.env` stays in `.gitignore`.

## Tech debt

- [ ] `datetime.utcnow()` in [conversation_service.py:32](app/services/conversation_service.py#L32) is deprecated in Python 3.12; replace with `datetime.now(UTC)`.

## Observability / tooling (to analyse)

- [ ] **Evaluate LangSmith vs Langfuse and choose** — both provide LLM tracing: per-call input/output, latency, tokens, cost, graph traces, prompt versioning, datasets for evals. Decision points:
  - **LangSmith**: closed-source SaaS by LangChain. Zero-config integration (env vars). Best graph visualisation for LangGraph. Data leaves our infra.
  - **Langfuse**: open-source, self-hostable (Docker). Vendor-neutral (works with any LLM lib). Self-host = better fit for sensitive user data (newcomers, possibly BSN/DigiD context).
  - **Pre-decision action**: until we choose, attach metadata to every LLM call (`run_name`, `metadata={"conversation_id": ..., "user_id": ..., "source_node": ...}`). Both tools use that for filtering/grouping — essentially free now, saves work later.
  - **Do not yet**: hard-code vendor-specific callbacks. Keep LLM invocations on the standard LangChain interface so we can wire either tool in via config.

## Product / architecture documentation

- [ ] Write higher-level product and architecture documents (separate, deliberate effort, not a 5-minute job): `project-brief-v1.md`, `mvp-scope-v1.md`, `technical-architecture-v1.md`, `data-model-v1.md`, `user-stories-v1.md`, `implementation-plan-v1.md`. Decide first where they live (one level above the repo, or inside `docs/product/`), then link them from the README.

## Follow-up on the LangGraph router

- [ ] Add a system prompt / Yara persona to the router (language, tone, support-agent context, default municipality Den Haag).
- [ ] Error handling when the OpenAI call fails — send a fallback message to the user instead of crashing the webhook.
- [ ] Token limit / history truncation: today we send the recent history as-is. Smarter context strategy: summarisation, sliding window, semantic retrieval.
- [ ] Support media messages in the router: download PDFs/photos from `MediaUrl0`, store them under `storage/uploads/`, attach via `media_storage_path`. Extract text for PDFs (pypdf).
- [ ] Use `WorkflowState` actively: persist current workflow type and step per conversation so the router can branch (intake, DigiD subflow, document flow).
- [ ] Debug endpoint `GET /debug/conversation/{phone_number}` for a quick readable dump of a conversation (alternative to opening a DB GUI).

## Migrated to Issues

_(empty)_

## Done

- [x] Contextual LLM reply (GPT-4o) via LangGraph router instead of static reply. Conversation history loaded from Postgres ([app/workflows/router.py](app/workflows/router.py)).
- [x] End-to-end test of the router workflow via WhatsApp succeeded.
- [x] `source_node` column on `messages`; outbound messages now record which workflow node produced them. LLM invocations attach `run_name` and `metadata` for future LangSmith/Langfuse integration.
