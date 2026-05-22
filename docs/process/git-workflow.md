# Git workflow

## Backlog → Issue (refinement on demand)

The moment we decide to start work on something:

1. Pick an item from `BACKLOG.md`.
2. Create a GitHub Issue: `gh issue create` using the body from `docs/process/story-template.md`.
3. Move the line in `BACKLOG.md` to the `## Migrated to Issues` section with the issue link.
4. Write a spec in `docs/specs/<slug>.md` (template: `docs/process/spec-template.md`).
5. Continue with branch + implement (below).

Items only become Issues when they are actually being picked up — the backlog stays a low-ceremony idea buffer.

## Branches

- `main` is always shippable. Never push directly.
- Branch off `main` for every change. Naming:
  - `feature/<slug>` — new functionality
  - `fix/<slug>` — bug fix
  - `chore/<slug>` — tooling, deps, configs
  - `docs/<slug>` — documentation only
  - `refactor/<slug>` — internal change, no behavior delta

Keep slugs short and kebab-case: `feature/yara-system-prompt`, `fix/webhook-race`, `chore/upgrade-langgraph`.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <subject>

<optional body>

<optional footer(s)>
```

Allowed types: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `style`, `build`, `ci`, `perf`.

Subject: imperative mood, lowercase, no trailing period, ≤72 chars.

Examples:

```
feat(router): add system prompt for Yara persona
fix(webhook): handle empty message body without crashing
chore: introduce coding process docs and dev tooling
refactor(message-service): extract direction-to-langchain mapping
```

Commit at logical units — one commit per coherent change. Keep unrelated changes in separate commits.

## Pull requests

1. Push your branch: `git push -u origin feature/<slug>`
2. Open a PR against `main` via `gh pr create`
3. PR title follows the same Conventional Commit format as the squash-merge commit will use
4. PR body references the Issue (`Closes #<n>`) and links to the spec
5. Run `/ultrareview` to get an automated audit trail
6. Squash-merge once green; delete the branch after merge
7. Close the Issue (auto-closed if `Closes #<n>` is in the PR body)

## Never

- Force-push to `main`
- Rebase or rewrite history that has been pushed to a shared branch
- Use `--no-verify` to skip hooks
- Merge without running `ruff check` and `ruff format --check` locally

## Quick cheatsheet

```bash
# start work
git switch main && git pull
git switch -c feature/<slug>

# during work
.venv/bin/ruff check . && .venv/bin/ruff format .
git add <files>
git commit -m "feat(scope): <subject>"

# wrap up
git push -u origin feature/<slug>
gh pr create --title "feat(scope): <subject>" --body "Closes #<n>. Spec: docs/specs/<slug>.md"
# run /ultrareview, then squash-merge in GitHub UI
git switch main && git pull && git branch -d feature/<slug>
```
