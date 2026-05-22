# Yara — working agreements for Claude

Read this at the start of every session.

## What Yara is

WhatsApp-first support agent for newcomers in The Hague (Den Haag). Stack: FastAPI + LangGraph + Postgres + Twilio. See [README.md](README.md) for setup and details.

## Read this first

- [BACKLOG.md](BACKLOG.md) — idea buffer (not yet promoted to GitHub Issue)
- [CHANGELOG.md](CHANGELOG.md) — recent changes
- [docs/process/](docs/process/) — git, spec, and story templates
- [docs/specs/](docs/specs/) — one spec file per feature
- Active work: run `gh issue list` for GitHub Issues

## Per-feature workflow

For **every** feature, even small ones:

1. **Create an Issue**: `gh issue create` using the body from [docs/process/story-template.md](docs/process/story-template.md)
2. **Write a spec**: `docs/specs/<slug>.md` based on [docs/process/spec-template.md](docs/process/spec-template.md)
3. **Branch**: `feature/<slug>`, `fix/<slug>`, `chore/<slug>`, or `docs/<slug>`
4. **Implement** — pythonic, simple, readable (see code style below)
5. **Lint + format**: `.venv/bin/ruff check . && .venv/bin/ruff format .`
6. **Update CHANGELOG.md** in the `[Unreleased]` section
7. **Commit** using Conventional Commits format
8. **PR** to `main` → run `/ultrareview` → squash-merge → close the Issue

For trivial fixes (≤5 minutes), the spec may be a single short paragraph in the Issue body — but the CHANGELOG entry is still required.

## Code style

Pythonic, simple, readable:

- **Type hints everywhere**. Use `str | None` (PEP 604), not `Optional[str]`.
- **No comments unless WHY** (not WHAT) — well-named identifiers already explain what the code does.
- **Short functions** with a single responsibility.
- **No premature abstraction** — three similar lines beat a premature helper.
- **No backwards-compat shims** for code that does not run anywhere yet.
- **No barrel files** — import directly from where the symbol is defined.
- **Module-private helpers** start with `_`.

Linter: ruff. Config lives in `pyproject.toml`. Run before every commit.

## Conventional Commits

```
feat: ...        new user-facing functionality
fix: ...         bug fix
docs: ...        documentation only
refactor: ...    code change without behavior change
chore: ...       tooling, deps, configuration
test: ...        adding/changing tests
style: ...       formatting (rare — ruff handles most)
build: ...       build system or external deps
ci: ...          CI configuration
perf: ...        performance improvement
```

Subject in imperative mood, lowercase, no trailing period.

Example: `feat(router): add system prompt for Yara persona`

## Git strategy (summary)

- `main` is always shippable
- Trunk-based: branch off `main`, squash-merge back
- Run `/ultrareview` before merging — provides an audit trail
- Never force-push to `main`

Full details: [docs/process/git-workflow.md](docs/process/git-workflow.md).

## Testing approach

No automated tests yet. Until a test suite exists: verify end-to-end via the real WhatsApp flow or `curl` against `/webhooks/twilio/whatsapp`. When tests do arrive: `pytest` in `tests/`, mirroring the `app/` structure.

## Tools

- **Venv**: `.venv/` with Python 3.12.13 (matches Docker)
- **DB GUI**: TablePlus recommended (connect to `localhost:5432`, user/pass/db = `yara/yara/yara`)
- **GitHub CLI**: `gh` for Issues and PRs. **Requires `gh auth login` once per machine** before Issues or PRs can be created.
- **Migrations**: `docker compose exec app alembic upgrade head`
- **Pre-commit hooks**: `.venv/bin/pre-commit install && .venv/bin/pre-commit install --hook-type commit-msg` once per clone. Hooks run on every commit: ruff (lint + format), commit-msg validation (Conventional Commits), gitleaks (secret scan).
- **CI**: GitHub Actions in `.github/workflows/ci.yaml`. On every PR: ruff check + format, gitleaks, and a check that `feat:` or `fix:` PRs touch `CHANGELOG.md`.

## Do not do without checking first

- Force-push or rewrite history on `main`
- Add or downgrade dependencies
- Roll back migrations against a live database
- Modify or commit `.env`
- Restructure the README

## Communication language

The user prefers Dutch for conversation, but **all written artifacts (code, docs, commit messages, PR descriptions, files in the repo) are in English**.

## Memory

Cross-session preferences live in [/Users/elyonpeacfield/.claude/projects/-Users-elyonpeacfield-Documents-Projects-yara/memory/](file:///Users/elyonpeacfield/.claude/projects/-Users-elyonpeacfield-Documents-Projects-yara/memory/). Check `MEMORY.md` there.
