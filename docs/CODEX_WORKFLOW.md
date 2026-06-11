# Codex workflow

## VS Code flow

1. Open this repository in VS Code.
2. Install the recommended extensions from `.vscode/extensions.json`.
3. Run `uv sync` once from the repository root.
4. Select the uv-created interpreter from `.venv`.
5. Open the Codex sidebar.
6. Trust the project so `.codex/config.toml` and `AGENTS.md` are loaded.
7. Paste `.codex/prompts/00-kickoff.md`.
8. Review the plan Codex proposes.
9. Let Codex implement the MVP.
10. Review diffs before accepting all edits.
11. Run `make check` locally.
12. Continue with prompts `01` through `04`.

## CLI flow

From the repo root:

```bash
codex
```

Then paste:

```text
Read AGENTS.md and .codex/prompts/00-kickoff.md, then implement that task. Use uv and Ruff exactly as documented in docs/TOOLING.md.
```

## Task slicing

Use one Codex thread per prompt file. Avoid running two threads that edit the same files at the same time.

## Verification

Codex should run commands through `uv run` or `make`:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

The full gate is:

```bash
make check
```

## Good follow-up prompts

```text
Show me the generated schema diff between the fixture and current output. Do not edit files yet.
```

```text
Add tests for this edge case first, then implement the smallest change to pass them.
```

```text
Review the converter for non-deterministic ordering. Fix only confirmed issues.
```

```text
Run uv run ruff check . and uv run ruff format --check ., then fix only tooling violations.
```
