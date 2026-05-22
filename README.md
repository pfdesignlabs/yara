# Yara

Yara is a WhatsApp-first guidance assistant prototype for newcomers in The Hague.

The product is designed to help users understand official communication, identify what matters, and take the next right step. Rather than a generic chatbot, Yara is being built as a conversational workflow system focused on clarity, action, reminders, and follow-up over time.

## Project goal

This repository contains the prototype implementation for the first technical version of Yara. The current goal is to build a convincing prototype that demonstrates:

- inbound WhatsApp communication,
- structured user and conversation handling,
- message persistence,
- action-oriented architecture,
- and a path toward document understanding, follow-up, and local support routing.

## Current status

Yara has a working end-to-end WhatsApp loop with an LLM-backed reply.

### Implemented

- Docker-based local runtime
- FastAPI app + PostgreSQL + Alembic migrations
- SQLAlchemy models for `User`, `Conversation`, `Message`, `WorkflowState`, `Document`
- Twilio WhatsApp inbound webhook + payload normalisation
- Automatic user creation by phone number
- Automatic active-conversation creation
- Inbound and outbound message persistence
- LangGraph router (`app/workflows/router.py`) calling GPT-4o with conversation history loaded from Postgres
- Per-message `source_node` tracking on outbound messages
- Observability metadata on every LLM call (`run_name`, `conversation_id`, `user_id`) ready for LangSmith or Langfuse
- ngrok-based public webhook testing

### Verified working

- A real WhatsApp message sent through the Twilio Sandbox reaches the local app via ngrok
- The app normalises the inbound payload and persists it in Postgres
- The router produces a contextual reply using recent history from the database
- The reply is sent back through Twilio and persisted with `source_node = "process"`

## Architecture summary

- **Runtime**: Docker Compose with a FastAPI app service and a Postgres service.
- **Messaging**: Twilio WhatsApp (sandbox). Inbound payloads are normalised into internal models before any business logic runs, so additional channels can plug in later without coupling to Twilio.
- **Workflow**: LangGraph in `app/workflows/`. Today there is one node (`process`). The graph will grow into a router that branches per intent.
- **Persistence**: Postgres stores users, conversations, and every inbound/outbound message. Conversation history is the source of truth — the in-memory conversation in the LLM call is derived from it.
- **State**: a `workflow_states` table exists for per-conversation workflow state but is not actively used yet.

## Repository structure

```text
yara/
  app/
    api/            # FastAPI routers
    core/           # config (pydantic-settings)
    db/             # SQLAlchemy base, session
    integrations/   # Twilio client + payload normalisation
    models/         # SQLAlchemy models
    schemas/        # Pydantic schemas
    services/       # User / conversation / message services
    workflows/      # LangGraph routers (router.py)
    main.py
  alembic/
    versions/       # database migrations
  docs/
    process/        # git workflow + spec/story templates
    specs/          # per-feature specs
  storage/
    uploads/        # downloaded media (per future feature)
  .env              # not committed
  alembic.ini
  BACKLOG.md
  CHANGELOG.md
  CLAUDE.md
  docker-compose.yml
  Dockerfile
  pyproject.toml    # ruff config
  requirements.txt
  requirements-dev.txt
```

## How we work

- Working agreements for development sessions live in [CLAUDE.md](CLAUDE.md).
- Git, spec, and story templates live in [docs/process/](docs/process/).
- The backlog of unrefined ideas lives in [BACKLOG.md](BACKLOG.md). Active tickets live in GitHub Issues (`gh issue list`).
- Notable changes are recorded in [CHANGELOG.md](CHANGELOG.md).
- Code style is enforced by `ruff` (config in [pyproject.toml](pyproject.toml)). Run `.venv/bin/ruff check . && .venv/bin/ruff format .` before committing.

## Local development

### Requirements

- Docker Desktop
- ngrok
- Twilio account with WhatsApp Sandbox enabled
- Python 3.12 venv for running scripts/tests outside Docker (optional)

### Start the stack

```bash
docker compose up --build
```

### Health check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Expose the local webhook

```bash
ngrok http 8000
```

Configure the Twilio WhatsApp Sandbox inbound webhook to point to:

```text
https://<your-ngrok-domain>/webhooks/twilio/whatsapp
```

### Local Python venv (optional, for scripts)

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Configuration

Configuration is loaded by `pydantic-settings` from the environment (and `.env` as fallback). Key variables:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_NUMBER`
- `UPLOADS_DIR`

The prototype uses the Twilio WhatsApp Sandbox sender as the outbound `from` address.

## Database and migrations

Alembic is configured. Initial migrations have been created and applied.

### Generate a new migration

```bash
docker compose exec app alembic revision --autogenerate -m "describe change"
```

### Apply migrations

```bash
docker compose exec app alembic upgrade head
```

## What is not implemented yet

The prototype is intentionally narrow. See [BACKLOG.md](BACKLOG.md) for the full list. Highlights still missing:

- Twilio request-signature validation
- Media download + document understanding pipeline
- Yara system prompt / persona
- Error handling on OpenAI failures
- Multi-node router (intake, DigiD prerequisite, document flow)
- Action creation, reminders, worker-based follow-up
- LangSmith / Langfuse integration

## Security notes

This repository is still prototype-stage software.

- The Twilio webhook does not yet verify request signatures.
- File retention policy for `storage/uploads/` is not defined.
- Rotate any credentials in `.env` before broader use.

## Product direction

Yara is not intended to become a generic chatbot. The long-term direction is:

- understand difficult letters,
- identify urgency conservatively,
- generate clear next steps,
- follow up over time,
- help users find relevant local support,
- and support communication with institutions through multilingual draft assistance.

Conversation is the interface. Workflow state is the product.
