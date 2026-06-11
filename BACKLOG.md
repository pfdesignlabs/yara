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

- [ ] **[Later] [2026-06-04]** Doc_helper gives repetitive, identical status replies to bare "hi" / check-in messages — once a document's actions are closed, every subsequent standalone greeting gets the same "the objection is already marked as done" answer (observed across 5+ days in one tester conversation). Make it more human and varied: a short greeting, or proactively invite the user to share a new letter, instead of re-stating the closed workflow each time.
  - **Relevant when:** a tester conversation shows repeated greetings after a workflow closes (already observed), **or** before real users return to the bot for new letters.

## Graph & router redesign

> **Tracked as epic [#62](https://github.com/pfdesignlabs/yara/issues/62)** — the build steps below split into their own sub-issues when the pilot starts.

The router is a **dispatcher** that inspects user + workflow state and picks the specialist node — but today it **freezes after intake** (`matched_workflow` set once → permanently `document_helper`, no chat, no case lifecycle). The redesign replaces this with a **dynamic, case-lifecycle-aware dispatch** + a **phased doc_helper** + a new **Case** domain entity, and adds the **two-sided** caseworker dimension. Prototyped end-to-end mock-first in `scratch_doc_flow.py`: dynamic router + intent-classifier; a discovery ReAct subgraph; a doc_helper with a within-turn ReAct loop **and** a cross-turn phase machine (OFFER→EXPLAIN→DEEPEN→ACTIONS→EMAIL→REMINDERS→DONE that *lingers* in DEEPEN); and an orchestrator that simulates webhook + `run_router` with a persistent world (= `WorkflowState` + `Case`). Design: `workspace/working/graph-praatplaat.md`. Plan: `~/.claude/plans/deep-inventing-pancake.md`. The old "continue-or-switch dialogue" and "intent classifier for free chat" router items are **prototyped here** (the dynamic dispatch + intent-classifier are exactly those) — only app-integration remains, tracked below.

- [ ] **[Later] [2026-06-10]** Case domain model + migration. New `cases` table (id, user_id, topic, `goal_dod`, `summary`, status `active|on_hold|closed`, closed_at) + a **nullable `case_id` FK** on `documents` / `actions` / `reminders` (additive, orthogonal to the existing polymorphic `source_id`/`target_id`). Runtime (`phase`, `active_specialist`, `active_case_id`) lives in the **PostgresSaver-checkpointer**, not in `WorkflowState` — 3-way split: checkpointer = runtime, OLTP = domain, EVENT-log = history (zie praatplaat §5.2). Extends to **Plan** + **Event** entities (zie §5.4). Foundation for everything below.
  - **Relevant when:** starting the redesign app-integration (step 1); pilot phase, not before the pitch.
- [ ] **[Later] [2026-06-10]** Integrate the redesign prototype into `app/`. Replace the freeze-after-intake `run_router` with the dynamic dispatch; compile discovery + the phased doc_helper as subgraphs called from thin wrappers (RouterState ↔ sub-state translation); add the SET-active-case orchestration, the conversational `case_manager`, and soft case-close. Adopt the PostgresSaver-checkpointer for runtime-state + `interrupt()` (human-in-the-loop). Reuse the existing tool / reminder / metadata services. Keep the current demo stable for the pitch.
  - **Relevant when:** the Case model has shipped **and** we are in the pilot phase (a deliberate deepening, not pre-pitch).
- [ ] **[Later] [2026-06-10]** Per-node prompts for the redesign nodes in `prompts.yaml` (the "finetune pass"). Each real node gets its own entry: `intent_classifier` (internal), `onboarding` (extractor + speaker), `discovery`, `case_match`, `disambiguation`, `case_manager` (client), and the phase-aware `doc_helper` agent (one base prompt + per-phase focus blocks — phases are values of `phase`, **not** separate nodes). The scratch has only an inline intent-classifier prompt; the rest are mock.
  - **Relevant when:** the structure is wired end-to-end in `app/` (finetune against a working whole, not in isolation).
- [ ] **[Later] [2026-05-24]** Multiple active workflows / concurrent cases — today the model is one active `WorkflowState` per user. The Case lifecycle covers sequential cases; decide whether to allow *concurrent* flows (e.g. intake still incomplete while a document arrives) and how to swap focus, pause/resume, or queue. Likely a `priority` or `last_active_at` signal + explicit user-confirmation language.
  - **Relevant when:** ≥2 specialist workflows exist **and** a logged conversation shows a user triggering workflow B while workflow A is still incomplete.
- [ ] **[Later] [2026-05-22]** Free-chat / fallback specialist node — handles messages that don't fit a named flow (the safety net when intake / case_manager / a specialist do not apply). Working name TBD: `general_chat`, `fallback_specialist`, `default_chat`.
  - **Relevant when:** logs show users sending messages outside every named flow more than a handful of times (fallback usage signal).
- [ ] **[Later] [2026-05-22]** Token limit / history truncation: today we send the recent history as-is. Smarter context strategy: summarisation, sliding window, semantic retrieval. (With the checkpointer, also decide whether messages live in the checkpoint or stay in the `messages` table.)
  - **Relevant when:** average conversation history exceeds ~30 messages, **or** observed truncated/cut-off LLM responses, **or** per-turn cost climbs.
- [ ] **[Later] [2026-06-10]** `langgraph.prebuilt` is broken in the pinned langgraph version — `ToolNode` / `tools_condition` import `langgraph._internal._runnable`, a module that does not exist (version skew between the langgraph core and its `prebuilt` package, in both the host venv and the container). Never surfaced because the app hand-rolls its own tool loop (`document_helper._invoke_with_tool_loop`) and never imports `langgraph.prebuilt`. Blocks the redesign plan's assumption of the prebuilt `ToolNode`. Fix: realign/upgrade langgraph (verify the existing graphs still compile) **or** keep hand-rolling the tool node + a `tools_condition` equivalent (what the scratch + app already do).
  - **Relevant when:** the redesign app-integration needs a tool node (decide bump-vs-hand-roll then).

## Features

- [ ] **[Later] [2026-05-22]** DigiD prerequisite subflow — deterministic routing for users who don't have DigiD yet.
  - **Relevant when:** trusted public-service source indexing exists (we need accurate DigiD process info), **and** ≥1 logged conversation shows a user blocked by missing DigiD.
- [ ] **[Later] [2026-05-24]** Intake captures `migration_status` / `residence_status` (e.g. statushouder, asielzoeker, kennismigrant) — used by the DigiD prerequisite subflow and other status-dependent routing. Out of scope for the first intake; the first intake covers language, household, country of origin, personal situation, and information need only.
  - **Relevant when:** starting work on the DigiD prerequisite subflow (this is its main intake-side input).
- [ ] **[Later] [2026-05-22]** Trusted public-service source indexing (official Dutch government sources) — the validated leading-source index that grounds answers. Infrastructure (Firecrawl scraper + LLM-refiner + trust-gate) exists in `scripts/knowledge/`; the **validated Haagse index is pilot-work with the gemeente** ("gemeente bepaalt de leidende bronnen") and is not yet wired into the app's answering. Feeds the redesign's research specialist.
  - **Relevant when:** Yara produces a confidently-wrong statement about a government process in ≥1 logged conversation, **or** before any deployment to real users, **or** when the gemeente confirms leading sources (Q&A 4).

## Security, privacy & compliance

- [ ] **[Later] [2026-06-04]** Production storage for user uploads — today inbound WhatsApp media is written to a hardcoded `/app/storage/uploads/<user_id>/...` on local disk ([attachment_service.py](app/services/attachment_service.py)), unencrypted and not durable across redeploys. These are sensitive PII (IND/gemeente/debt letters: BSN, financial and residence data). For production: object storage (S3/GCS-style) with encryption-at-rest, access control, and a configurable bucket/path. Pairs with the retention policy below.
  - **Relevant when:** before exposing the bot to real users, **or** when the app runs on more than one instance / an ephemeral container.
- [ ] **[Later] [2026-05-22]** File retention policy for `storage/uploads/` (max retention period, periodic cleanup).
  - **Relevant when:** the first real user uploads a file, **or** within 30 days of the first stored upload.
- [ ] **[Later] [2026-06-05]** Data minimisation — store only the extracted fields (sender, type, deadline, action) rather than the full raw document, and/or expire the raw upload after processing. Less raw PII at rest = smaller breach surface + simpler compliance. Touches the data model and depends on the gemeente's retention/minimisation expectations (Q&A 12b).
  - **Relevant when:** the gemeente confirms retention/minimisation expectations, **or** before real users.
- [ ] **[Later] [2026-06-05]** EU data residency for the LLM — uploaded document text currently goes to OpenAI (US). For production, use OpenAI's EU data-residency / region option (and EU-only Postgres hosting) so the chapter-V transfer story is clean.
  - **Relevant when:** before real users, **or** if the gemeente requires EU/NL hosting (Q&A 12).
- [ ] **[Later] [2026-06-05]** Email body leaks to TinyURL — `draft_mail` POSTs the full `mailto:` URL (the user's personal situation, bilingual) to `tinyurl.com` to shorten it, sending sensitive personal data to a US URL-shortener on every drafted mail. For production, revert to a self-hosted redirect (the removed `mail_drafts` table + `GET /m/{token}` endpoint) or a shortening approach that keeps the data in-house.
  - **Relevant when:** before real users, **or** as part of the DPIA sub-processor review.
- [ ] **[Later] [2026-06-05]** Operational ntfy pushes leak PII — the new-user event push sends the tester's phone number to ntfy.sh (a public push service; a secret topic is not access control). Anonymise the push (drop the phone number / use an internal id) or move to an authenticated or self-hosted channel.
  - **Relevant when:** before real users, **or** as part of the DPIA sub-processor review.
- [ ] **[Later] [2026-05-22]** Rotate credentials in `.env` before any broader use; double-check `.env` stays in `.gitignore`.
  - **Relevant when:** before deploying to a real audience, **or** if there is any suspicion of credential exposure.

## Observability, monitoring & cockpit

The cockpit is the single auth-gated operator surface for running and tuning Yara — read side = the operational + conversation-quality dashboard; write side = prompt/settings + tester data management. It sits on top of structured logs + the (future) event log. **PII-grens per publiek:** the ops surface is PII-light; the tester/data surface is consent-driven, scoped, and access-logged.

- [ ] **[Later] [2026-06-04]** Production-grade health monitoring to replace the launchd watchdog stopgap (`scripts/monitoring/`). The current setup is single-host (only runs while this Mac is awake), self-heals by shelling out to `docker compose` / `open -a Docker`, and leans on ngrok-free + secrets staged out of `.env`. For production: container `restart: unless-stopped` + Docker autostart; an external uptime monitor (healthchecks.io / UptimeRobot) pinging `/health` + the public URL off-host; structured error tracking (Sentry) instead of log-grepping; a stable ingress so the Twilio webhook never needs a manual update.
  - **Relevant when:** before exposing the bot to non-test users, **or** when the test host can no longer be relied on to stay awake.
- [ ] **[Later] [2026-06-04]** Real-time new-user (and other business) events from the app instead of the 5-min DB poll in `scripts/monitoring/events/notify_events.sh`. Emit the ntfy push (or a generic event hook) from the user-creation path in the webhook so a new tester is announced instantly, and so other events (first document, reminder fired, mail drafted) can ride the same channel. Pairs with the **Event log** from the redesign.
  - **Relevant when:** the 5-min latency becomes annoying, **or** we want more than just new-user events.
- [ ] **[Later] [2026-06-10]** Capture Twilio message delivery/read status. The app persists `whatsapp_message_id` but no delivery state, so checking whether a tester received/opened a message means querying Twilio's REST API ad-hoc (`sent → delivered → read`). Wire a Twilio `StatusCallback` URL + persist the status on the message row, so delivery/read is visible in the DB + the cockpit. Note: `read` only appears if the recipient has read receipts enabled.
  - **Relevant when:** building the monitoring dashboard, **or** when "did the tester actually get it?" recurs.
- [ ] **[Later] [2026-05-22]** **Evaluate LangSmith vs Langfuse and choose** — both provide LLM tracing (per-call I/O, latency, tokens, cost, graph traces, prompt versioning, eval datasets). **LangSmith**: closed SaaS by LangChain, zero-config, best LangGraph viz, data leaves our infra. **Langfuse**: open-source, self-hostable, vendor-neutral, better fit for sensitive user data. *Pre-decision action (free now):* attach `run_name` + `metadata` to every LLM call (already done in `run_router`). *Do not yet:* hard-code vendor-specific callbacks.
  - **Relevant when:** shipping to ≥3 test users, **or** when LLM cost exceeds €20/month, **or** when prompt iterations lack comparison data.
- [ ] **[Later] [2026-06-04]** Cockpit — prompt + settings management. View and edit the per-node prompts (`prompts.yaml`) and per-node settings (`model`, `temperature` from `get_node_config`) from the admin UI, with change history so edits are auditable + revertible. An operator (incl. a non-author domain expert) should read every node's prompt and safely tweak copy/tone without touching the repo. Also: allowed languages, reminders on/off + sandbox cap, feature toggles, per-node model. Depends on moving prompts to a DB-backed store (see prompt-loader hardening + structured-fields tech-debt).
  - **Relevant when:** the edit→commit→redeploy loop slows prompt iteration, **or** a non-author needs to tune copy.
- [ ] **[Later] [2026-06-04]** Cockpit — operational dashboard. One live screen for what the watchdog + events scripts push to ntfy and what `analyze.py` prints: stack health (app/db, ngrok URL, OpenAI canary, Twilio balance, uptime), tester activity (users, conversations, in/outbound volume, pending reminders), recent errors, and a per-user drill-down with the conversation-quality eval.
  - **Relevant when:** the CLI + ntfy combination no longer gives a fast enough picture, **or** before an operator other than the maintainer needs visibility.
- [ ] **[Later] [2026-06-04]** Cockpit — tester / data management. List testers (status, language, last activity), open a readable transcript, and perform GDPR data-subject actions (export + erasure) per user — erasure must remove both DB rows **and** stored upload files (today a manual DB delete leaves orphaned files, observed when deleting a tester). Gives the right-to-erasure / access requirement an actual operator path. Pairs with a tester allowlist once Twilio signature validation lands.
  - **Relevant when:** the first erasure/access request is plausible (any non-test user), **or** manual DB edits on live data happen more than occasionally.
- [ ] **[Later] [2026-05-22]** Debug endpoint `GET /debug/conversation/{phone_number}` for a quick readable dump of a conversation (a lightweight precursor to the cockpit transcript view).
  - **Relevant when:** debugging via TablePlus / direct DB queries happens more than ~3× per session and starts feeling annoying.
- [ ] **[Later] [2026-05-22]** Set up a GitHub Project for visual work tracking. Overkill for current solo / single-Issue throughput.
  - **Relevant when:** active Issues exceed 5 at the same time, **or** a second contributor joins the repo.

## Tech debt

- [ ] **[Later] [2026-05-27]** Re-extract `preferred_language` after intake completes. Today `state_extractor_node` only runs during intake; after `matched_workflow` is set the language slot is frozen. Doc_helper mitigates this in its prompt by following the latest user message's language, but the slot stays stale — affects logging, reminder body language, and any future specialist. **Worse on a photo-first conversation:** when the first message is a document, the router fast-forwards intake straight to doc_helper, so `state_extractor_node` never runs and the language is *never captured at all* (observed with tester Nienke — replied "Nederlands", slot stayed `None`). Options: (a) lightweight language detector on every inbound, (b) re-trigger `state_extractor_node` on language-only updates, (c) move `preferred_language` to a per-turn derived value.
  - **Relevant when:** a second specialist needs the language slot, **or** reminder body language drifts, **or** (already observed) a photo-first user's `preferred_language` stays `None`.
- [ ] **[Later] [2026-05-27]** Switch doc_helper tool-trigger pattern from MVP-direct to explicit-confirmation for production. Today the prompt calls `mark_action_done` and `create_reminder` directly when context is clear; only `draft_mail` requires a confirmation turn. For production, all action-mutating tools (at minimum `create_reminder`) should follow propose-in-text → confirm → tool-call so side effects only happen after explicit assent.
  - **Relevant when:** before shipping to real users, **or** after the first run where the LLM mis-triggers a tool from ambiguous text.
- [ ] **[Later] [2026-05-27]** Jinja2 templating for `reminder.body_template`. Today the dispatcher sends the column value verbatim — the `_template` suffix is aspirational. When a reminder needs to interpolate context (`"Heb je {{action.description}} al gedaan?"`), wire `jinja2` into the dispatcher and render against a context dict from the linked action / conversation / user.
  - **Relevant when:** the first reminder use-case needs dynamic content, **or** copy drifts because the same hardcoded body repeats across tool calls.
- [ ] **[Later] [2026-05-27]** Support stand-alone reminders without a `conversation_id`. Today the dispatcher logs+skips reminders where `conversation_id IS NULL` because `create_outbound_message` requires a conversation. Options: (a) auto-create a conversation per fire, (b) reuse the user's latest conversation, (c) relax the constraint and tag the row differently.
  - **Relevant when:** a use case appears for proactive nudges not tied to an active conversation (e.g. "weekly check-in"), **or** the LLM creates reminders without conversation context.
- [ ] **[Later] [2026-05-23]** Replace cron with a production-grade scheduler (apscheduler, Celery + Redis, Kubernetes CronJobs) for the proactive reminder sender. Cron lacks retries, observability, distributed safety, and a dead-letter queue.
  - **Relevant when:** the reminder sender ships **and** more than ~10 active reminders exist, **or** observed missed reminders due to transient failures.
- [ ] **[Later] [2026-05-27]** Row-level locking in `list_due_reminders` / `mark_reminder_sent`. The dispatcher relies on `max_instances=1` in APScheduler to prevent double-sends. Once the scheduler is no longer single-instance we need `SELECT ... FOR UPDATE SKIP LOCKED` or a `scheduled → claimed → sent` status transition.
  - **Relevant when:** the production-grade scheduler upgrade ships, **or** when we observe the first duplicate WhatsApp send.
- [ ] **[Later] [2026-05-23]** Harden the `app/prompts/` loader to type-safe access (Pydantic model parsing the YAML on load, or an Enum of keys). The current `get("dotted.key")` lookup surfaces typos only at runtime and offers no IDE autocomplete.
  - **Relevant when:** the YAML grows beyond ~15 keys, **or** ≥2 runtime `KeyError`s from typoed prompt keys, **or** a non-author needs to find/modify prompts, **or** A/B / per-tenant prompt variations are needed (then go straight to a DB or LangSmith Hub backing).
- [ ] **[Later] [2026-05-28]** Split `node_task` into structured fields per node in `prompts.yaml`. Each node's prompt is one large free-text block; the `document_helper_node` block grew to ~80 lines mixing goal, output, tone, tool policy, interaction patterns, constraints. Proposed fields (pick ~5-7): `goal`, `output_structure`, `tone`, `tool_policy`, `interaction_patterns`, `constraints`, optional `examples`, composed with XML-style tags in `get_node_prompt` (gpt-5-class models follow tagged sections more reliably). Keep `node_task` as a fallback; migrate one node at a time, starting with `document_helper_node`. (Composes with the per-node-prompts redesign item.)
  - **Relevant when:** the next major prompt-engineering iteration, **or** when A/B testing prompt variations, **or** when a non-author needs to tweak prompts without grepping one huge block.
- [ ] **[Later] [2026-05-23]** Document the tool architectural pattern alongside specialist nodes — where tools live (`app/tools/`), how they wire into nodes' `bind_tools`, how the LLM is briefed, and how the terse internal-classifier base relates to tools called from client-facing nodes.
  - **Relevant when:** onboarding a contributor to the tool layer, **or** when the redesign's per-specialist tool subsets land.
- [ ] **[Later] [2026-05-27]** Polymorphic FK integrity at the DB layer for `actions.source_id` and `reminders.target_id`. The reference is application-level only — nothing prevents an `actions` row pointing at a non-existent `documents.id`. Options: per-source-type CHECK constraints with triggers, polymorphic inheritance, or pre-insert validators.
  - **Relevant when:** before exposing the bot to real users with logs they care about, **or** after the first integrity bug in scratch runs.
- [ ] **[Later] [2026-05-27]** Set up a `pytest` test-suite parallel to the scratch runners. Scratch tests are great for prompt iteration + live-DB CRUD; `pytest` with fixtures + transaction-rollback-per-test is the right pattern for CI-protected regression. Mirror `app/` under `tests/`. Wire into the GitHub Actions workflow.
  - **Relevant when:** ≥5 modules with non-trivial logic that change frequently, **or** before shipping a feature with privacy-sensitive data flowing through, **or** when a regression bites in scratch-only-tested code.
- [ ] **[Later] [2026-05-27]** Cleanup script for scratch_test rows. `DELETE FROM actions WHERE source_type LIKE 'scratch%_test'`, same for reminders. Could be `scripts/clean_scratch_data.py` or a make target. Scratch tests accumulate rows on every run.
  - **Relevant when:** scratch rows clutter DB introspection, **or** before sharing the dev DB with another developer.
- [ ] **[Later] [2026-05-22]** `datetime.utcnow()` is deprecated in Python 3.12 (used in `router.py`, `conversation_service.py`, model defaults); replace with `datetime.now(UTC)`.
  - **Relevant when:** upgrading to Python 3.13+ (where `utcnow` is removed), **or** when CI starts failing on deprecation warnings.

## Product / architecture documentation

- [ ] **[Later] [2026-05-22]** Repo-level product + architecture documents. `docs/architecture.md` (running system) + `docs/admin.md` (operator guide) now exist; the **tender strategy/product docs live in the private `workspace/`** (objective, synthese, plan-van-aanpak, MOA — gitignored). Still open: decide which of those graduate to a public, repo-level set (project-brief, mvp-scope, data-model, user-stories) and where they live, then link from the README.
  - **Relevant when:** onboarding a second contributor, **or** before a stakeholder review that needs a public reference.

## Migrated to Issues

- [Epic: Case-centric graph redesign](https://github.com/pfdesignlabs/yara/issues/62) — #62 (tracking; build steps split off when the pilot starts)
- [Race condition in `get_or_create_user_by_phone_number`](https://github.com/pfdesignlabs/yara/issues/54) — #54
- [Doc_helper mid-conversation language switch](https://github.com/pfdesignlabs/yara/issues/55) — #55
- [Reminder dates non-deterministic — anchor in code](https://github.com/pfdesignlabs/yara/issues/56) — #56
- [GDPR/AVG DPIA + sub-processor review](https://github.com/pfdesignlabs/yara/issues/57) — #57
- [Validate the Twilio request signature](https://github.com/pfdesignlabs/yara/issues/58) — #58
- [Conversation quality evaluation + learning loop](https://github.com/pfdesignlabs/yara/issues/59) — #59
- [Broaden structlog beyond the hot-path](https://github.com/pfdesignlabs/yara/issues/60) — #60
- [Self-host Firecrawl for the knowledge scraper](https://github.com/pfdesignlabs/yara/issues/61) — #61
- [doc_helper: explain freshly-uploaded documents after prior chat](https://github.com/pfdesignlabs/yara/issues/51) — #51 (fixed, PR #52)
- [doc_helper: surface all pending actions, not just the current document's](https://github.com/pfdesignlabs/yara/issues/45) — #45 (fixed, PR #46)
- [Document helper specialist node (PDF + image vision)](https://github.com/pfdesignlabs/yara/issues/11) — #11 (bundles: media download, pypdf text extraction, document-explainer node, multi-image-as-pages assembly, per-node LLM creation)
- [Intake workflow + minimal router dispatch](https://github.com/pfdesignlabs/yara/issues/7) — #7 (bundles: bring back intake workflow, actively use WorkflowState, new-vs-existing user check, active workflow lookup)
- [System prompt + error-handling fallback](https://github.com/pfdesignlabs/yara/issues/4) — #4
- [Remove tracked `__pycache__/*.pyc` files](https://github.com/pfdesignlabs/yara/issues/2) — #2

## Done

- [x] **Per-node LLM creation** — `llm_for_node(node_name)` reads `model` + `temperature` from `get_node_config` and builds a cached `ChatOpenAI` per `(model, temperature)` (`app/workflows/_llm.py`). Replaced the single module-level client.
- [x] Reminder creation tool (`create_reminder`), reminder sender (APScheduler cron dispatcher over Twilio), and mail-drafting tool (`draft_mail` with `mailto:` + AI-disclosure) — all shipped and running in production (doc_helper v2).
- [x] Contextual LLM reply via LangGraph router instead of static reply. Conversation history loaded from Postgres ([app/workflows/router.py](app/workflows/router.py)).
- [x] End-to-end test of the router workflow via WhatsApp succeeded.
- [x] `source_node` column on `messages`; outbound messages record which workflow node produced them. LLM invocations attach `run_name` + `metadata` for future LangSmith/Langfuse integration.
