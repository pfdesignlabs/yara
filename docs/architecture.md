# Architecture

How Yara turns an inbound WhatsApp message into a reply. This is the technical
map of the running system; for *why* the product is shaped this way, see the
README. For day-to-day operation, see [admin.md](admin.md).

## At a glance

```
WhatsApp ──► Twilio ──► POST /webhooks/twilio/whatsapp (FastAPI)
                              │
              normalize → user/conversation → (media? download + Document)
                              │
                     persist inbound message
                              │
                       run_router()  ── LangGraph ──┐
                              │                      │
                       send WhatsApp reply ◄─────────┘
                              │
                     persist outbound message

         APScheduler (every 1 min) ──► dispatch due reminders ──► Twilio
```

- **Runtime**: Docker Compose — FastAPI + Postgres + APScheduler in one app
  container, Postgres in another. Exposed to Twilio via an ngrok tunnel in the
  test phase.
- **Persistence**: Postgres. **Conversation history is the source of truth** —
  the graph reloads it on every turn rather than holding in-memory state.
- **LLM**: OpenAI via LangChain; the conversation flow is a LangGraph state
  machine.

## Request flow — one inbound turn

Entry point: [`twilio_whatsapp_webhook`](../app/api/routes.py). Each inbound
message runs synchronously through:

1. **Normalize** the Twilio form payload → internal model
   ([twilio_whatsapp.py](../app/integrations/twilio_whatsapp.py)).
2. **User + conversation**: `get_or_create_user_by_phone_number`,
   `get_or_create_active_conversation`.
3. **Media** (if any): `download_twilio_media` writes the file to
   `storage/uploads/<user_id>/…` and `create_document` extracts PDF text
   ([attachment_service.py](../app/services/attachment_service.py)).
4. **Persist** the inbound message; `touch_conversation`.
5. **Typing indicator** sent back to Twilio (cleared automatically when the
   reply lands).
6. **`run_router`** ([router.py](../app/workflows/router.py)) produces
   `(reply_text, source_node)`.
7. **Send** the reply via the Twilio outbound API and persist it, tagged with
   the `source_node` that produced it.

## Conversation graph (LangGraph)

`run_router` rebuilds state from the DB, invokes a compiled `StateGraph`, then
persists what changed. The graph:

```
START → router ─┬─ intake_flow → state_extractor → intake_node → END
                ├─ doc_helper  → document_helper_node            → END
                └─ chat        → chat_node                       → END
```

The **router node** picks the branch ([router.py](../app/workflows/router.py)):

- intake not finished → **intake_flow** (extract slots, then the intake turn)
- `slots.matched_workflow == "document_helper"` → **doc_helper**
- otherwise → **chat** (free conversation once intake is done)

`RouterState` carries the recent messages (last 10), the intake `slots`,
`intake_done`, a `documents` snapshot (only when routed to doc_helper), and a
`replying_to_reminder` snapshot. Notable edges in `run_router`:

- **Intake fast-forward**: if a document is uploaded while intake is still
  running, intake is auto-completed and `matched_workflow` set to
  `document_helper`, so the upload reaches the specialist instead of being
  swallowed by another intake question.
- **Failure is contained**: any exception returns the `fallbacks.llm_error`
  prompt tagged `error_fallback`, so the user always gets a reply.

### Nodes

| Node | File | Role |
|---|---|---|
| `state_extractor` | [intake_extractor.py](../app/workflows/intake_extractor.py) | extracts intake slots (language, situation, matched_workflow) from the conversation |
| `intake_node` | [intake.py](../app/workflows/intake.py) | the intake turn — two-step language picker, prototype intro |
| `document_helper_node` | [document_helper.py](../app/workflows/document_helper.py) | explains a shared document, drives actions/reminders/mail via tools |
| `chat_node` | [router.py](../app/workflows/router.py) | free-chat fallback after intake |

Each node's model + bound tools come from a YAML prompt config
([prompts/](../app/prompts/)); `get_node_prompt` / `get_node_config` /
`llm_for_node` resolve them per node.

## Tools

LangChain `@tool`s bound to specialist nodes ([tools/](../app/tools/)):

- **`mark_action_done`** — closes a tracked action.
- **`create_reminder`** — schedules a proactive follow-up (picked up by the
  scheduler).
- **`draft_mail`** — produces a bilingual email + a tappable, TinyURL-shortened
  `mailto:` link with a mandatory AI-disclosure footer.

## Reminders (proactive flow)

Separate from the conversational graph. APScheduler
([scheduler/cron.py](../app/scheduler/cron.py)) ticks every minute and
[`reminder_dispatcher`](../app/scheduler/reminder_dispatcher.py) sends due
reminders through the Twilio outbound API. Replies to a reminder are detected on
the next inbound turn and surfaced to the LLM via `replying_to_reminder`.

## Data model

Postgres, via SQLAlchemy ([models/](../app/models/)). Migrations in
[alembic/](../alembic/).

| Table | Holds |
|---|---|
| `user` | phone number, display name, preferred language, municipality, status |
| `conversation` | one active thread per user; `last_message_at` |
| `message` | every inbound/outbound turn — the source of truth; `source_node`, media refs |
| `document` | uploaded files: storage path, mime, extracted text, processing status |
| `action` | tracked to-dos extracted from a document (status, urgency, deadline) |
| `reminder` | scheduled proactive follow-ups (target, `scheduled_for`, status, `sent_at`) |
| `workflow_state` | intake progress + extracted `slots` (`state_json`), completion |

## Integrations & config

- **Twilio** — inbound webhook normalized in
  [twilio_whatsapp.py](../app/integrations/twilio_whatsapp.py); outbound replies,
  typing indicator, and reminder sends via
  [twilio_client.py](../app/integrations/twilio_client.py).
- **OpenAI** — through `langchain_openai`, model per node from the prompt config.
- **Config** — [config.py](../app/core/config.py): pydantic-settings, loaded from
  `.env` (`DATABASE_URL`, `OPENAI_API_KEY`, `TWILIO_*`, …).
