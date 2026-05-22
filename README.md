# Yara

Yara is a WhatsApp-first guidance assistant prototype for newcomers in The Hague.

The product is designed to help users understand official communication, identify what matters, and take the next right step. Rather than acting as a generic chatbot, Yara is being built as a conversational workflow system focused on clarity, action, reminders, and follow-up over time.

## Project Goal

This repository contains the prototype implementation for the first technical version of Yara.

The current goal is to build a convincing prototype that demonstrates:
- inbound WhatsApp communication,
- structured user and conversation handling,
- message persistence,
- action-oriented architecture,
- and a path toward document understanding, follow-up, and local support routing.

The prototype is intended to support a challenge submission and should optimize for:
- believable product behavior,
- clean technical foundations,
- fast iteration,
- and strong demo readiness.

## Current Status

Yara currently has a working first end-to-end WhatsApp integration loop.

### Implemented
- Docker-based local runtime
- FastAPI application scaffold
- PostgreSQL database
- SQLAlchemy model layer
- Alembic migration setup
- Relational models for:
  - `User`
  - `Conversation`
  - `Message`
  - `WorkflowState`
  - `Document`
- Twilio WhatsApp inbound webhook
- Twilio payload normalization layer
- Real inbound message persistence
- Real outbound message persistence
- Automatic user creation by phone number
- Automatic active conversation creation
- LangGraph-based intake routing
- Intake memory with `situation_summary`
- Explicit intake `open_loop` tracking
- Early structured DigiD prerequisite fact tracking
- Low-information continuation guardrail for more natural follow-up turns
- Document download, storage, extraction, and understanding pipeline
- Document-aware reply generation
- ngrok-based public webhook testing

### Verified working
- A real WhatsApp message can be sent through Twilio Sandbox
- The message reaches the local app through ngrok
- The app normalizes the inbound payload
- The app persists inbound and outbound message state in PostgreSQL
- The app sends a WhatsApp reply back through Twilio
- A real Twilio `MessageSid` is stored for inbound and outbound traffic
- Intake context now carries forward across turns through workflow state

## Architecture Summary

Yara is being built as a small containerized application.

### Runtime
- Docker Compose
- FastAPI app service
- PostgreSQL database
- Worker service scaffold

### Core architecture principles
- WhatsApp-first interface
- Multi-user safe by design
- User-scoped memory and persistence
- Workflow-oriented backend
- Provider-specific logic isolated from product logic
- Structured state in Postgres
- AI and retrieval layered on top of deterministic workflow boundaries
- guided journeys should use structured state and deterministic route decisioning

### Integration approach
Twilio is currently used as the first messaging provider.

The architecture intentionally normalizes inbound provider payloads into internal application models before business logic runs. This allows future support for additional messaging channels without tightly coupling core workflows to Twilio-specific field structures.

## Repository Structure

```text
yara/
  app/
    api/
    core/
    db/
    integrations/
    models/
    prompts/
    retrieval/
    schemas/
    services/
    utils/
    workflows/
    main.py
  alembic/
    versions/
  data/
    samples/
    seed/
  migrations/
  scripts/
  storage/
    uploads/
  tests/
  worker/
    jobs/
    main.py
  .env
  .env.example
  alembic.ini
  docker-compose.yml
  Dockerfile
  requirements.txt
  README.md
```

## Local Development

### Requirements
- Docker Desktop
- ngrok
- Twilio account with WhatsApp Sandbox enabled

### Start the stack
```bash
docker compose up --build
```

### Health check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"ok"}
```

### Expose local webhook
```bash
ngrok http 8000
```

Then configure the Twilio WhatsApp Sandbox inbound webhook to point to:

```text
https://<your-ngrok-domain>/webhooks/twilio/whatsapp
```

## Configuration

Configuration is managed through environment variables.

Important variables include:
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_NUMBER`
- `UPLOADS_DIR`

The current prototype uses the Twilio WhatsApp Sandbox sender as the outbound `from` address.

## Database and Migrations

Alembic is configured and the initial migration has already been created and applied.

### Generate a new migration
```bash
docker compose run --rm app alembic revision --autogenerate -m "describe change"
```

### Apply migrations
```bash
docker compose run --rm app alembic upgrade head
```

## What Is Not Implemented Yet

The current version is intentionally still narrow.

Not yet implemented:
- action model and reminder execution flow
- support resource retrieval layer
- full DigiD guided subflow with deterministic prerequisite routing
- workflow transitions driven by document understanding
- Twilio signature validation
- production-grade error handling and retries

## Immediate Next Steps

The recommended next implementation steps are:

1. Let document understanding influence workflow transitions more explicitly
2. Refine general intake completion and handoff into specific journeys
3. Build a dedicated DigiD prerequisite subflow with structured facts and deterministic route selection
4. Start constrained ingestion of trusted public-service sources (DigiD, Gemeente Den Haag, IND, Rijksoverheid, Belastingdienst)
5. Add action creation from document understanding
6. Add reminder scheduling and worker-based follow-up
7. Introduce support resource retrieval and matching as support for workflow decisions
8. Add Twilio signature validation and harden error handling

## Security Notes

This repository is still prototype-stage software.

Important current limitations:
- Twilio webhook signature validation has not yet been implemented
- uploaded file retention policy is not yet defined
- operational secrets hygiene should be tightened before broader use

If credentials were exposed during development, rotate them before any broader deployment or collaboration.

## Product Direction

Yara is not intended to become a generic chatbot.

The long-term product direction is:
- understand difficult letters,
- identify urgency conservatively,
- generate clear next steps,
- follow up over time,
- help users find relevant local support,
- and support communication with institutions through multilingual draft assistance.

Conversation is the interface.
Workflow state is the product.

## Related Project Docs

Higher-level product and architecture documents live one directory above this project folder and include:
- `project-brief-v1.md`
- `mvp-scope-v1.md`
- `technical-architecture-v1.md`
- `data-model-v1.md`
- `user-stories-v1.md`
- `implementation-plan-v1.md`

These documents define the current product scope, architecture direction, and implementation path.
