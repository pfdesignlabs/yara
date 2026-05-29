# Yara

Yara is a WhatsApp-first guidance assistant prototype for newcomers in The Hague.
It reads letters from Dutch institutions (gemeente, IND, Belastingdienst,
schuldhulpverlening, energy providers, debt collectors) and helps the user
understand what the letter means, what they need to do, and by when.

The product is a conversational workflow on top of WhatsApp, built around four
verbs the user actually experiences:

- **explain** a letter in their own language at B1 reading level,
- **act** on it through tools — set proactive reminders, draft a reply email,
- **follow up** when the deadline approaches by sending a check-in reminder,
- **route** the user to the right local support when professional help is needed
  (Juridisch Loket, Bureau Sociaal Raadslieden, Schuldhulpverlening Den Haag,
  Geldfit, …).

## User journey

```
User                                                 Yara
─────────                                            ────────
"Hi"                                              →  Language picker (Dutch, English, العربية,
                                                     Türkçe, Українська, ትግርኛ, … pick one)
"English"                                         →  One-line intro ("I'm Yara, this is a prototype
                                                     for letters from Dutch institutions")
                                                     + "What letter can I help you with?"
"A letter from the energy company"                →  "Send it as a PDF or photo, I'll explain it."
[PDF upload]                                      →  • Summary of the letter
                                                     • 1–2 concrete next steps with deadlines
                                                     • Pointers to local support
                                                     • Soft offer: "Want me to help draft a reply?"
"Yes please"                                      →  Interview — one targeted question per turn
"…answers…"                                       →  Keeps asking until enough context, then a
                                                     short values-summary for the user to confirm
"Looks good"                                      →  Composes a bilingual email (user-language +
                                                     Dutch), shortens through TinyURL, returns a
                                                     tap-to-open link. Sets a reminder for the
                                                     deadline.
[next morning at 10:00]                           →  Friendly check-in: "We were going to send the
                                                     objection — did you manage?"
"Yes!"                                            →  Marks the action done, closes the loop.
```

## Capabilities the prototype demonstrates

- **Multilingual intake** — explicit language picker on the first turn instead of guessing.
- **Document understanding** — both PDF text and photo-of-letter (multi-page) via gpt-5.5 vision.
- **Structured action extraction** — the LLM produces `document_type`, `urgency`,
  `deadline_date`, and a list of `ActionDraft`s with their own deadlines and types,
  persisted as `actions` rows.
- **Tool-using specialist** — `document_helper_node` can call three tools and
  knows when each applies:
  - `create_reminder` — schedules a check-in on the action's deadline
  - `draft_mail` — drafts a bilingual email through a short-link redirect so it
    fits in a single WhatsApp message
  - `mark_action_done` — closes an action when the user confirms it succeeded
- **Proactive cron-driven reminders** — APScheduler ticks every minute and a
  reminder dispatcher (Twilio) sends due reminders, marks them sent, and the
  router recognises the user's reply as a follow-up to that reminder.
- **Tone-aware composition** — explicit warmth requirements in the prompt
  (no UPPERCASE headers, acknowledge stress, plain-language B1 level), plus
  hard guards against hallucinated email addresses or made-up deadlines.
- **WhatsApp UX touches** — typing indicator on inbound (so the user sees
  "Yara is typing…" during LLM calls), automatic message-splitting if a body
  exceeds the 1600-char Twilio limit, and an AI-disclosure footer
  automatically appended to every drafted email.

## Test scenarios

Two ready-to-upload demo letters live in [test-assets/](test-assets/):

- [`eneco-aanmaning.pdf`](test-assets/eneco-aanmaning.pdf) — final reminder
  from an energy company with an open balance. Exercises the whole flow:
  payment deadline (reminder), `betalingsregeling@eneco.nl` for objections
  (mail-interview path), and explicit "verdere hulp" pointers to Geldfit,
  Schuldhulpverlening Den Haag, Sociaal Raadslieden.
- [`ind-aanvullingen.pdf`](test-assets/ind-aanvullingen.pdf) — IND request
  for missing documents on a pending residence-permit application. Tests
  the same flow on a more bureaucratic letter with multiple required
  attachments.

## Local development

### Requirements

- Docker Desktop
- ngrok (public URL for the Twilio webhook)
- Twilio account with WhatsApp Sandbox enabled
- OpenAI API key with access to `gpt-5.5` and `gpt-5.4`

### Start the stack

```bash
docker compose up --build
```

### Expose the webhook

```bash
ngrok http 8000
```

Point the Twilio WhatsApp Sandbox inbound webhook to
`https://<your-ngrok-domain>/webhooks/twilio/whatsapp`.

### Health check

```bash
curl http://localhost:8000/health
```

## Architecture summary

- **Runtime**: Docker Compose with FastAPI + Postgres + APScheduler.
- **Messaging**: Twilio WhatsApp (sandbox). Inbound payloads are normalised
  into internal models before any business logic runs.
- **Workflow**: LangGraph in `app/workflows/`. Nodes:
  `router_node → state_extractor_node → intake_node` for first-contact intake,
  and `router_node → document_helper_node` once the user shares a document.
  `extract_doc_metadata_node` runs once per new document for structured
  action extraction.
- **Tools**: `app/tools/` exposes `mark_action_done`, `create_reminder`,
  `draft_mail`. `TOOL_REGISTRY` + `tools_for_node()` drive `bind_tools(…)`
  based on the YAML config per node.
- **Persistence**: Postgres for users, conversations, messages, documents,
  actions, reminders. Conversation history is the source of truth.
- **Scheduler**: APScheduler with a `SQLAlchemyJobStore` ticks every minute
  and dispatches due reminders through Twilio.

## Configuration

`pydantic-settings` loads from environment / `.env`. Key variables:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`

## What is intentionally not in this prototype

The prototype is narrow on purpose. Highlights tracked in [BACKLOG.md](BACKLOG.md):

- Twilio request-signature validation
- Structured logging across all modules
- LangSmith / Langfuse observability integration
- Production-grade scheduler (Celery / Kubernetes CronJobs)
- Switch from MVP-direct to explicit-confirmation pattern for action-mutating tools
- pytest suite parallel to the live-DB scratch runners

## How we work

- Working agreements for development sessions: [CLAUDE.md](CLAUDE.md)
- Git, spec, story templates: [docs/process/](docs/process/)
- Backlog of unrefined ideas: [BACKLOG.md](BACKLOG.md)
- Notable changes: [CHANGELOG.md](CHANGELOG.md)
- Code style: `ruff` (config in [pyproject.toml](pyproject.toml))

## Security notes

This is prototype-stage software.

- Twilio webhook does not yet verify request signatures.
- File retention policy for `storage/uploads/` is not defined.
- AI-drafted emails always include a transparency footer noting they were drafted with help from Yara.
- Rotate credentials in `.env` before broader use.

## Product direction

Yara is not a generic chatbot. The long-term direction is to understand any
letter from a Dutch institution, identify what matters and by when, generate
a clear next step, follow up over time, and route the user to relevant local
support — with communication assistance when the user needs to reply.

Conversation is the interface. Workflow state is the product.
