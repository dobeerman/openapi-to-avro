# AGENTS.md

## Project mission

Build a deterministic Python CLI that converts OpenAPI JSON/YAML specs into a single self-contained Avro schema for GET method responses only.

## Always read first

Before implementation work, inspect:

- `docs/PROJECT_BRIEF.md`
- `docs/TECHNICAL_SPEC.md`
- `docs/AVRO_MAPPING.md`
- `docs/TOOLING.md`
- `docs/ACCEPTANCE_CRITERIA.md`
- `tests/fixtures/minimal.openapi.json`
- `tests/fixtures/expected-minimal.avsc`

## Engineering rules

- Prefer small, reviewable changes.
- Use `uv` for dependency management and command execution. Do not replace the uv workflow with ad hoc `pip install` instructions.
- Keep `uv.lock` checked in. Refresh it with `uv lock` after dependency changes.
- Use Ruff for both formatting and linting. Do not add Black, Flake8, isort, autoflake, or yapf.
- Do not add production dependencies unless they are already listed in `pyproject.toml`, or you explain why they are needed first.
- Add development dependencies under `[dependency-groups].dev`, not `[project.optional-dependencies]`.
- Keep output deterministic: stable path ordering, stable generated names, stable JSON formatting.
- Preserve configured response-code order exactly; when multiple statuses are selected, include non-numeric statuses like `default` with deterministic PascalCase name suffixes.
- Treat ambiguous OpenAPI constructs conservatively. In strict mode, fail loudly with actionable errors instead of inventing lossy mappings.
- When adding Avro unions for optional, nullable, `oneOf`, or allowed `anyOf` schemas, flatten union branches instead of producing nested Avro union arrays.
- Do not silently rename enum values in strict mode.
- Preserve OpenAPI descriptions in Avro `doc` where possible.
- Keep public functions typed.

## Verification commands

Run these before claiming the task is complete:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

For a full local check, use:

```bash
make check
```

If a tool is unavailable in the current environment, explain that and run the closest available subset.

## Implementation boundaries

- Target Python 3.11+.
- The root envelope fields are fixed unless a test or spec explicitly says otherwise.
- The `data` field must be an Avro union of named records generated from GET responses.
- Only `application/json` success responses are included by default.
- POST, PUT, PATCH, DELETE, OPTIONS, HEAD, and TRACE paths are ignored.
