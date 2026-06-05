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
- [ ] **[Next] [2026-06-04]** Doc_helper does not follow a mid-conversation language switch — when the user switches from English to Dutch (or vice versa) partway through, Yara keeps replying in the original intake language. Observed repeatedly in a tester conversation (user writes Dutch, Yara answers English). The prompt-level mitigation noted in the `preferred_language` slot tech-debt item below is not reliably working in practice — strengthens the case for re-detecting language per inbound message.
  - **Relevant when:** observed (already seen); pairs with the "Re-extract `preferred_language` after intake" tech-debt item.
- [ ] **[Later] [2026-06-04]** Doc_helper gives repetitive, identical status replies to bare "hi" / check-in messages — once a document's actions are closed, every subsequent standalone greeting gets the same "the objection is already marked as done" answer (observed across 5+ days in one tester conversation). Make it more human and varied: a short greeting, or proactively invite the user to share a new letter, instead of re-stating the closed workflow each time.
  - **Relevant when:** a tester conversation shows repeated greetings after a workflow closes (already observed), **or** before real users return to the bot for new letters.

## Features

- [ ] **[Later] [2026-05-22]** DigiD prerequisite subflow — deterministic routing for users who don't have DigiD yet.
  - **Relevant when:** trusted public-service source indexing exists (we need accurate DigiD process info), **and** ≥1 logged conversation shows a user blocked by missing DigiD.
- [ ] **[Later] [2026-05-24]** Intake captures `migration_status` / `residence_status` (e.g. statushouder, asielzoeker, kennismigrant) — used by the DigiD prerequisite subflow and other status-dependent routing. Out of scope for the first intake; the first intake covers language, household, country of origin, personal situation, and information need only.
  - **Relevant when:** starting work on the DigiD prerequisite subflow (this is its main intake-side input).
- [ ] **[Later] [2026-05-22]** Trusted public-service source indexing (official Dutch government sources).
  - **Relevant when:** Yara produces a confidently-wrong statement about a government process in ≥1 logged conversation, **or** before any deployment to real users.

## Router architecture (to refine further)

The router is not the LLM-that-replies — it is a **dispatcher** that inspects user and workflow state and chooses which specialist node handles the message. Mix of deterministic checks (DB queries) and LLM-based decisions where human nuance is needed.

Sub-items to refine before implementation:

- [ ] **[Next] [2026-05-22]** Continue-or-switch dialogue — when an active flow exists and the user sends something that doesn't obviously belong to it, decide whether to interrupt the flow, ask the user, or carry on. Likely small LLM-based classify step.
  - **Relevant when:** ≥2 specialist nodes exist (so "switch to what?" has a real answer).
- [ ] **[Later] [2026-05-24]** Multiple active workflows simultaneously — today the model is one active `WorkflowState` per user. Decide whether to allow concurrent flows (e.g. intake still incomplete while user uploads a document for document_helper), and how to swap focus, pause/resume, or queue. Likely involves a `priority` or `last_active_at` column and explicit user-confirmation language.
  - **Relevant when:** ≥2 specialist workflows exist **and** a logged conversation shows a user triggering workflow B while workflow A is still incomplete.
- [ ] **[Next] [2026-05-22]** Intent classifier for free chat — when intake is done and no active flow exists, classify the message into a coarse intent (document, question, urgent, smalltalk, …) and branch.
  - **Relevant when:** intake is done **and** ≥2 specialist nodes exist as routing destinations.
- [ ] **[Later] [2026-05-22]** Free-chat specialist node — handles messages that don't fit a named flow. Acts as the safety net when intake / document_helper / scheduling do not apply. Working name TBD; alternatives to weigh when implementing: `general_chat`, `unstructured_chat`, `fallback_specialist`, `default_chat`.
  - **Relevant when:** logs show users sending messages outside every named flow more than a handful of times (fallback usage signal).
## Security / hardening

- [ ] **[Next] [2026-05-22]** Validate the Twilio request signature on `/webhooks/twilio/whatsapp` — the endpoint currently accepts any incoming POST.
  - **Relevant when:** before the webhook URL is shared with anyone outside the maintainer (hard prerequisite for any non-personal use).
- [ ] **[Now] [2026-06-04]** GDPR/AVG + security compliance assessment before any non-test use. Yara processes special-category personal data (residence status, financial situation, debt) of vulnerable newcomers, and **sends uploaded document text to OpenAI (US)** for LLM processing. Research and document: lawful basis + (likely) a DPIA for high-risk processing; data-processing agreements / sub-processor terms with Twilio (WhatsApp) and OpenAI, incl. data residency and whether content is used for training; data minimisation (do we need to store the full document?); retention + right to erasure/access; consent/transparency wording for testers. Pulls together the security items below (signature validation, retention, encrypted storage, credential rotation) under one compliance bar.
  - **Relevant when:** before onboarding any non-test/real user — hard gate. Start the research now so it doesn't block launch.
- [ ] **[Later] [2026-05-22]** File retention policy for `storage/uploads/` (max retention period, periodic cleanup).
  - **Relevant when:** the first real user uploads a file, **or** within 30 days of the first stored upload.
- [ ] **[Later] [2026-06-04]** Production storage for user uploads — today inbound WhatsApp media is written to a hardcoded `/app/storage/uploads/<user_id>/...` on local disk ([attachment_service.py](app/services/attachment_service.py)), unencrypted and not durable across redeploys. These are sensitive PII (IND/gemeente/debt letters: BSN, financial and residence data). For production: object storage (S3/GCS-style) with encryption-at-rest, access control, and a configurable bucket/path instead of a hardcoded local path. Pairs with the retention policy above.
  - **Relevant when:** before exposing the bot to real users, **or** when the app runs on more than one instance / an ephemeral container.
- [ ] **[Later] [2026-05-22]** Rotate credentials in `.env` before any broader use; double-check `.env` stays in `.gitignore`.
  - **Relevant when:** before deploying to a real audience, **or** if there is any suspicion of credential exposure.

## Ops / monitoring

- [ ] **[Later] [2026-06-04]** Production-grade health monitoring to replace the launchd watchdog stopgap (`scripts/monitoring/`). The current setup is single-host (only runs while this Mac is awake), self-heals by shelling out to `docker compose` / `open -a Docker`, and leans on ngrok-free + secrets staged out of `.env`. For production: container `restart: unless-stopped` + Docker Desktop autostart for self-recovery; an external uptime monitor (healthchecks.io / UptimeRobot) pinging `/health` and the public URL from off-host; structured error tracking (Sentry) instead of log-grepping; and a stable ingress (reserved ngrok domain or a real host) so the Twilio webhook never needs a manual update.
  - **Relevant when:** before exposing the bot to non-test users, **or** when the test host can no longer be relied on to stay awake.
- [ ] **[Later] [2026-06-04]** Real-time new-user (and other business) events from the app instead of the 5-min DB poll in `scripts/monitoring/events/notify_events.sh`. Emit the ntfy push (or a generic event hook) from the user-creation path in the webhook handler so a new tester is announced instantly, and so other events (first document uploaded, reminder fired, mail drafted) can ride the same channel.
  - **Relevant when:** the 5-min latency becomes annoying, **or** we want more than just new-user events.
- [ ] **[Next] [2026-06-04]** Conversation quality evaluation + learning loop — grow the manual `scripts/monitoring/analyze.py` LLM eval into a real tool with its own home (e.g. `scripts/evaluation/` or a top-level `evaluation/`, separate from operational monitoring). Per conversation: transcript → rubric score (the 7 dimensions already exist) + concrete improvement points. Aggregate across conversations to surface structurally weak dimensions and recurring failure patterns with examples. Learning, layered: (1) a prioritised report feeding BACKLOG / prompt tweaks; (2) a persisted eval dataset (conversations + scores) so a prompt change can be regression-tested ("does this raise the scores?") and trends tracked over time. Prototype the eval behaviour in `scratch.py` first.
  - **Relevant when:** ≥10–20 real tester conversations exist to evaluate, **or** before iterating on prompts blind to whether changes actually help.
- [ ] **[Next] [2026-06-04]** Self-host Firecrawl locally for the knowledge scraper (`scripts/knowledge/scrape.py`). The cloud free tier rate-limits **crawl** jobs hard — a full watchlist run 429s after 1–2 crawls (scrapes are fine). The local images already exist on the machine (`firecrawl-api`, `firecrawl-nuq-postgres`, `firecrawl-playwright-service`); set up the compose/config, run on `localhost:8080`, and point `FIRECRAWL_API_URL=http://localhost:8080/v2`. The scraper already supports this (endpoint-agnostic) — no limits, no cost. Mitigated for now by 429 retry-with-backoff in the scraper.
  - **Relevant when:** we want to crawl the full watchlist regularly, **or** the cloud free-tier limits keep blocking crawls.

## Admin / cockpit

The single auth-gated operator surface ("the cockpit") for running and tuning Yara — replacing today's split between CLI tools (`analyze.py`), ntfy pushes, and editing prompts in code + redeploying. Read side = the operational dashboard; write side = prompt/settings and data management.

- [ ] **[Later] [2026-06-04]** Prompt + settings management — view and edit the per-node prompts (`app/prompts/prompts.yaml`) and per-node settings (`model`, `temperature` from `get_node_config`) from the admin UI, with change history so edits are auditable and revertible. Today changing a prompt means a code edit + redeploy; an operator (incl. a non-author domain expert) should be able to read every node's prompt and safely tweak copy/tone without touching the repo. Other settings worth surfacing: allowed languages, reminders on/off + the sandbox 24h-reminder cap, per-workflow feature toggles, and the global/per-node LLM model. Depends on moving prompts to a DB-backed store (today they are file-loaded — see the prompt-loader hardening + structured-fields tech-debt items).
  - **Relevant when:** the edit→commit→redeploy loop slows prompt iteration down, **or** a non-author needs to tune copy.
- [ ] **[Later] [2026-06-04]** Operational monitoring dashboard — one live screen for everything the watchdog + events scripts now push to ntfy and that `analyze.py` prints to a terminal: stack health (app/db, ngrok URL, OpenAI canary, Twilio balance, last tick + uptime), tester activity (total/new users, active conversations, inbound/outbound volume, pending reminders), recent app errors, and a per-user drill-down with the conversation-quality LLM eval. This is the read side of the cockpit; pairs with the conversation-quality eval + production-health-monitoring items in Ops / monitoring.
  - **Relevant when:** the CLI + ntfy combination no longer gives a fast enough picture, **or** before an operator other than the maintainer needs visibility.
- [ ] **[Later] [2026-06-04]** Tester / data management — from the cockpit: list testers (status, language, last activity), open a readable transcript, and perform GDPR data-subject actions (export + erasure) per user. Folds in the ad-hoc DB surgery we now do by hand (e.g. deleting a ghost user) and gives the right-to-erasure / access requirement from the [Now] GDPR item an actual operator path. Pairs with a tester allowlist once Twilio signature validation lands.
  - **Relevant when:** the first erasure/access request is plausible (any non-test user), **or** manual DB edits on live data happen more than occasionally.

## Tech debt

- [ ] **[Later] [2026-05-22]** `datetime.utcnow()` in [conversation_service.py:32](app/services/conversation_service.py#L32) is deprecated in Python 3.12; replace with `datetime.now(UTC)`.
  - **Relevant when:** upgrading to Python 3.13+ (where `utcnow` is removed), **or** when CI starts failing on deprecation warnings.
- [ ] **[Later] [2026-05-23]** Harden the `app/prompts/` loader to type-safe access (Pydantic model parsing the YAML on load, or an Enum of keys). Current setup uses a simple `get("dotted.key")` lookup — typos surface only at runtime and there is no IDE autocomplete on prompt keys.
  - **Relevant when:** **any** of the following — the YAML grows beyond ~15 keys, two or more runtime `KeyError`s from typoed prompt keys are observed in dev/prod, a non-author needs to find or modify prompts, cross-prompt invariants emerge (e.g. "every client-facing node must compose with `personas.client`"), **or** A/B testing / per-tenant prompt variations is needed (at that point skip Pydantic and go straight to a DB or LangSmith Hub backing).
- [ ] **[Later] [2026-05-28]** Split `node_task` into structured fields per node in `prompts.yaml`. Today each node's prompt is one large free-text block; over months of iteration the `document_helper_node` block grew to ~80 lines mixing goal, output structure, tone, tool policy, interaction patterns, and constraints. Proposed fields (pick ~5-7, not all): `goal` (1-2 sentences), `output_structure`, `tone`, `tool_policy` (per-tool when/how), `interaction_patterns` (per-turn-type rules), `constraints` (don't-do list), optional `examples`. Composer in `get_node_prompt` concatenates these with XML-style tags (`<goal>…</goal>`, `<tone>…</tone>`, etc.) — gpt-5-class models follow tagged sections more reliably than long flowing blocks. Keep `node_task` as a fallback so non-refactored nodes keep working; migrate one node at a time, starting with `document_helper_node`.
  - **Relevant when:** the next major prompt-engineering iteration starts, **or** when we want to A/B test prompt variations (changing only `tone` while holding `tool_policy` constant), **or** when a non-author needs to tweak prompts without grepping a single huge block.
- [ ] **[Later] [2026-05-23]** Document the tool architectural pattern alongside specialist nodes — where tools live (likely `app/tools/`), how they are wired into nodes' LLM bindings, how the LLM is briefed about them, and how `personas.tool` (terse, structured-output base for internal classifiers) relates to tools called from inside client-facing nodes. First instance will be the reminder creation tool.
  - **Relevant when:** just before implementing the first tool (currently the reminder creation tool).
- [ ] **[Later] [2026-05-23]** Replace cron with a production-grade scheduler (apscheduler, Celery + Redis, Kubernetes CronJobs, etc.) for the proactive reminder sender. Cron lacks retries, observability, distributed safety, and a dead-letter queue.
  - **Relevant when:** the reminder sender ships **and** more than ~10 active reminders exist, **or** observed missed reminders due to transient failures.
- [ ] **[Later] [2026-05-24]** Wire per-node LLM creation: read `model` and `temperature` from `get_node_config(node_name)` and instantiate a `ChatOpenAI` with those settings instead of the single module-level `llm = ChatOpenAI(model="gpt-4o", ...)`. Cache instances per `(model, temperature)` tuple so we do not allocate a new client per call.
  - **Relevant when:** the first node with a different model lands (the first `internal` node — likely `intent_classifier` or `router_node`).
- [ ] **[Later] [2026-05-27]** Polymorphic FK integrity at the DB layer for `actions.source_id` and `reminders.target_id`. Today the reference is application-level only — nothing prevents an `actions` row from pointing at a non-existent `documents.id`. Options: per-source-type CHECK constraints with triggers, polymorphic inheritance pattern (one base + per-type subtables), or pre-insert validators in the service layer.
  - **Relevant when:** before exposing the bot to real users with logs they care about, **or** after the first integrity-related bug shows up in scratch runs.
- [ ] **[Later] [2026-05-27]** Set up a `pytest` test-suite parallel to the scratch runners. Scratch tests are great for prompt iteration and live-DB CRUD validation; `pytest` with fixtures + transaction-rollback-per-test is the right pattern for CI-protected regression. Mirror `app/` structure under `tests/`. Wire into the existing GitHub Actions workflow.
  - **Relevant when:** ≥5 modules with non-trivial logic that change frequently, **or** before shipping any feature with privacy-sensitive data flowing through, **or** when a regression bites us in scratch-only-tested code.
- [ ] **[Later] [2026-05-27]** Cleanup script for scratch_test rows. `DELETE FROM actions WHERE source_type LIKE 'scratch%_test'`, same for reminders. Could be a `scripts/clean_scratch_data.py` or a make target. Today scratch tests accumulate rows on every run.
  - **Relevant when:** scratch rows clutter DB introspection in TablePlus / psql, **or** before sharing the dev DB with another developer.
- [ ] **[Later] [2026-05-27]** Jinja2 templating for `reminder.body_template`. Today the dispatcher sends the column value verbatim — the `_template` suffix is aspirational. When a reminder needs to interpolate context (e.g. `"Heb je {{action.description}} al gedaan?"` or a deadline-aware nudge), wire `jinja2` into the dispatcher and render the body against a context dict assembled from the linked action / conversation / user.
  - **Relevant when:** the first reminder use-case needs dynamic content (likely in doc_helper v2 / #14 follow-up flows), **or** when copy starts drifting because the same hardcoded body is repeated across tool calls.
- [ ] **[Later] [2026-05-27]** Support stand-alone reminders without a `conversation_id`. Today the dispatcher logs+skips reminders where `conversation_id IS NULL` because `create_outbound_message` requires a conversation. Options: (a) auto-create a new conversation per fire, (b) reuse the user's latest conversation, (c) relax the outbound-message constraint and tag the row differently. Decision depends on how the rendered message should appear in the user's history.
  - **Relevant when:** a use case appears for proactive nudges that are not tied to an active conversation (e.g. "weekly check-in"), **or** if the LLM starts creating reminders without a conversation context for any reason.
- [ ] **[Later] [2026-05-27]** Row-level locking in `list_due_reminders` / `mark_reminder_sent`. The dispatcher currently relies on `max_instances=1` in APScheduler to prevent double-sends. Once the scheduler is no longer single-instance (Celery, multiple replicas, ...) we need `SELECT ... FOR UPDATE SKIP LOCKED` semantics or a status transition like `scheduled → claimed → sent` to make the dispatch idempotent across workers.
  - **Relevant when:** the production-grade scheduler upgrade (already in BACKLOG) ships, **or** when we observe the first duplicate WhatsApp send in logs.
- [ ] **[Later] [2026-05-27]** Re-extract `preferred_language` after intake completes. Today `state_extractor_node` only runs during intake; after `matched_workflow` is set the language slot is frozen. Doc_helper now mitigates this in its prompt by following the language of the latest user message, but the slot itself stays stale — affects logging, reminder body language, and any future specialist that relies on `preferred_language`. **Worse on a photo-first conversation:** when the first message is a document, the router fast-forwards intake straight to doc_helper, so `state_extractor_node` never runs and the language is *never captured at all* (observed with tester Nienke — replied "Nederlands", slot stayed `None`). Options: (a) run a lightweight language detector on every inbound, (b) re-trigger `state_extractor_node` opportunistically on language-only updates, (c) move `preferred_language` out of `slots` and into a per-turn derived value.
  - **Relevant when:** a second specialist outside doc_helper needs the language slot, **or** when reminder body_template language drifts because the slot is wrong, **or** (already observed) a photo-first user's `preferred_language` stays `None`.
- [ ] **[Later] [2026-05-27]** Switch doc_helper tool-trigger pattern from MVP-direct to explicit-confirmation for production. Today the prompt instructs the LLM to call `mark_action_done` and `create_reminder` directly when the context is clear, and only `draft_mail` requires an explicit user-confirmation turn first. For a production rollout we want all action-mutating tools (at minimum `create_reminder`) to follow the propose-in-text → confirm → tool-call pattern: user remains in control, side effects (reminders that fire, statuses that flip) only happen after explicit assent.
  - **Relevant when:** before shipping to real users, **or** after the first scratch / E2E run where the LLM mis-triggers a tool from ambiguous user text.

## Logging / observability

- [ ] **[Next] [2026-06-05]** Broaden the structlog logging beyond the hot-path. Layer 1 shipped (#48): `app/core/logging.py` + per-turn contextvars binding + `inbound_received`/`outbound_sent` events + PII redaction. Remaining: give every service/workflow module a structlog logger and emit key events (intake completion, document download, router decision, tool calls), and decide whether to unify stdlib/uvicorn logs into the same JSON stream (requires teaching the watchdog to read the new format). Layer 2 (Langfuse LLM tracing) is tracked separately and deferred to the DPIA.
  - **Relevant when:** debugging needs more than the hot-path events, **or** when we set up off-host log shipping.

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
- [ ] **[Later] [2026-05-22]** Debug endpoint `GET /debug/conversation/{phone_number}` for a quick readable dump of a conversation (alternative to opening a DB GUI).
  - **Relevant when:** debugging via TablePlus / direct DB queries happens more than ~3× per debugging session and starts feeling annoying.

## Product / architecture documentation

- [ ] **[Later] [2026-05-22]** Write higher-level product and architecture documents (separate, deliberate effort, not a 5-minute job): `project-brief-v1.md`, `mvp-scope-v1.md`, `technical-architecture-v1.md`, `data-model-v1.md`, `user-stories-v1.md`, `implementation-plan-v1.md`. Decide first where they live (one level above the repo, or inside `docs/product/`), then link them from the README.
  - **Relevant when:** onboarding a second contributor, **or** when scope decisions become hard to make without a written reference, **or** before a stakeholder review.

## Migrated to Issues

- [doc_helper: surface all pending actions, not just the current document's](https://github.com/pfdesignlabs/yara/issues/45) — #45 (fixed, PR #46)
- [Document helper specialist node (PDF + image vision)](https://github.com/pfdesignlabs/yara/issues/11) — #11 (bundles: media download, pypdf text extraction, document-explainer node, multi-image-as-pages assembly, per-node LLM creation)
- [Intake workflow + minimal router dispatch](https://github.com/pfdesignlabs/yara/issues/7) — #7 (bundles: bring back intake workflow, actively use WorkflowState, new-vs-existing user check, active workflow lookup)
- [System prompt + error-handling fallback](https://github.com/pfdesignlabs/yara/issues/4) — #4
- [Remove tracked `__pycache__/*.pyc` files](https://github.com/pfdesignlabs/yara/issues/2) — #2

## Done

- [x] Reminder creation tool (`create_reminder`), reminder sender (APScheduler cron dispatcher over Twilio), and mail-drafting tool (`draft_mail` with `mailto:` + AI-disclosure) — all shipped and running in production (doc_helper v2).
- [x] Contextual LLM reply (GPT-4o) via LangGraph router instead of static reply. Conversation history loaded from Postgres ([app/workflows/router.py](app/workflows/router.py)).
- [x] End-to-end test of the router workflow via WhatsApp succeeded.
- [x] `source_node` column on `messages`; outbound messages now record which workflow node produced them. LLM invocations attach `run_name` and `metadata` for future LangSmith/Langfuse integration.
