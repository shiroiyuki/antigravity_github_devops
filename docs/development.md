# Developer & AI Agent Guide (`antigravity_github_devops`)

Operational instructions for contributors and AI coding agents modifying `antigravity_github_devops` itself.
For user overview and plugin installation, see [README.md](../README.md).

> Note: Because `antigravity_github_devops` is an Antigravity Plugin (`plugin.json` at root), repository-specific development instructions live under `docs/development.md` rather than root `AGENTS.md` so `agy plugin validate . --strict` passes cleanly without polluting downstream workspaces.

## Setup & Environment
- Pure Python 3 standard library + POSIX Bash (no third-party pip runtime dependencies).
- Prefer dynamic paths (`Path.home()`, `os.environ`, `$PLUGIN_ROOT`) — never hardcode user-specific absolute paths.

## Testing & Validation
Always run the full suite before committing or pushing:
- `python3 run_tests.py`
- `python3 -m compileall -q hooks skills tests`
- `python3 skills/github-docs-guard/scripts/doc_audit.py --target . --strict`
- `agy plugin validate . --strict`

## Code & Modification Conventions
- Keep functions small, single-purpose, and covered by `unittest` tests under `tests/` or `skills/*/tests/`.
- Preserve `hooks/devops_guard.py` hook contract (`decision`: `allow` | `deny` | `force_ask`).
- Update `README.md`, `plugin.json`, or `rules/github_release_standards.md` when adding or changing skills, hooks, or CI templates.

## Safety Boundaries
- Never commit secrets, tokens, `.env`, `*hosts.yml`, or `CLAUDE.local.md`.
- Never run `git push --force` / `-f` or push `v*` release tags without explicit user confirmation.
