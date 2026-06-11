# Tooling

## Why uv

`uv` is the project entry point for Python tooling. It owns dependency resolution, the virtual environment, lockfile generation, and command execution.

The intended workflow is:

```bash
uv sync
uv run pytest
uv run ruff check .
```

This avoids environment drift between a developer terminal, VS Code, and Codex. If Codex can run a command, it should run the same command a human would run.

## Lockfile policy

`uv.lock` is part of the repository contract and should be committed.

Refresh it only when one of these changes:

- Runtime dependencies in `[project].dependencies`.
- Development dependencies in `[dependency-groups].dev`.
- Python compatibility requirements.
- Build backend requirements.

Use:

```bash
uv lock
```

For normal development, use:

```bash
uv sync
```

## Dependency policy

Runtime dependencies live in:

```toml
[project]
dependencies = []
```

Development-only dependencies live in:

```toml
[dependency-groups]
dev = []
```

Do not reintroduce `[project.optional-dependencies].dev` for the default development environment. Optional dependencies are for installable package extras, not the standard Codex/developer toolchain.

## Why Ruff

Ruff is used as the single Python style tool:

- Formatting.
- Import sorting.
- Linting.
- Safe auto-fixes.

Do not add Black, isort, Flake8, autoflake, or yapf unless the project explicitly changes this decision.

## Common commands

```bash
uv run ruff format .          # apply formatting
uv run ruff format --check .  # verify formatting
uv run ruff check .           # lint
uv run ruff check --fix .     # apply safe lint fixes
uv run mypy src               # type check source package
uv run pytest                 # run tests
make check                    # run the full local gate
```

## CI notes

`.github/workflows/ci.yml` uses the same commands as local development with `--locked` so CI fails when `pyproject.toml` and `uv.lock` drift.

The CI gate is:

```bash
uv sync --locked
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest
```

## VS Code notes

Run `uv sync` before opening or configuring the interpreter.

Use this interpreter on macOS/Linux:

```text
.venv/bin/python
```

Use this interpreter on Windows:

```text
.venv\Scripts\python.exe
```

The workspace config sets Ruff as the Python formatter and asks the Ruff extension to use the executable from the project environment.

## Codex notes

Codex should prefer `make` targets or `uv run` commands. It should not activate the virtual environment manually unless it is diagnosing a local editor problem.

Good command examples:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest tests/test_minimal_conversion.py tests/test_cli_contract.py
```
