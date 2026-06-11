# OpenAPI GET to Avro Envelope Generator

This repository is a Codex-ready starter kit for building a deterministic CLI that converts JSON/YAML OpenAPI specifications into a single self-contained Avro schema.

The generator only includes GET method paths. Each selected GET response becomes one named Avro record branch in the root envelope field named `data`.

## Tooling baseline

This project uses:

- `uv` for Python version pinning, dependency resolution, locking, virtual environment management, and command execution.
- `ruff` for linting, import sorting, and formatting.
- `mypy` for static type checking.
- `pytest` for tests.

Do not install dependencies with `pip install -e '.[dev]'` during normal development. Use the checked-in `uv.lock` and run project commands through `uv run`.

## Target CLI

```bash
uv run openapi-get-avro generate \
  --input examples/minimal.openapi.json \
  --namespace com.example.sports \
  --rootname SportsEnvelope \
  --output build/sports-envelope.avsc
```

## Expected root shape

```json
{
  "type": "record",
  "namespace": "com.example.sports",
  "name": "SportsEnvelope",
  "doc": "Generated from OpenAPI GET responses",
  "fields": [
    { "name": "id", "type": { "type": "string", "logicalType": "uuid" } },
    { "name": "timestamp", "type": { "type": "long", "logicalType": "timestamp-millis" } },
    { "name": "operation", "type": { "type": "enum", "name": "Operation", "symbols": ["CREATED", "UPDATED", "DELETED"] } },
    { "name": "entity_type", "type": { "type": "enum", "name": "EntityType", "symbols": ["MATCH"] } },
    { "name": "data", "type": [ { "type": "record", "name": "GetMatchResponse", "fields": [] } ] }
  ]
}
```

Avro does not use a literal `oneof` keyword. Use an Avro union, represented by a JSON array, for the `data` field.

## Local development

Install `uv`, then sync the project:

```bash
uv sync
```

Run the checks through the uv-managed environment:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

The same commands are wrapped by `make`:

```bash
make sync
make check
```

Useful commands:

```bash
uv run ruff format .       # format files
uv run ruff check --fix .   # apply safe lint fixes
uv lock                     # refresh uv.lock after dependency changes
uv tree                     # inspect the resolved dependency graph
```

## VS Code setup

Open this folder in VS Code and install the recommended extensions from `.vscode/extensions.json`.

After `uv sync`, select the interpreter at:

```text
.venv/bin/python
```

On Windows, select:

```text
.venv\Scripts\python.exe
```

Ruff is configured as the formatter for Python files. The workspace settings make save-time formatting use the project Ruff version from `.venv`.

## Suggested Codex kickoff

Open this folder in VS Code, install or open the Codex IDE extension, then paste the contents of `.codex/prompts/00-kickoff.md` into Codex.

The first implementation milestone is to make this pass:

```bash
uv run pytest tests/test_minimal_conversion.py tests/test_cli_contract.py
```

Then continue with the prompts under `.codex/prompts/` in numeric order.
