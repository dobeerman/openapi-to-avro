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

## CLI usage

```bash
uv run openapi-get-avro generate \
  --input examples/minimal.openapi.json \
  --namespace com.example.sports \
  --rootname SportsEnvelope \
  --output build/sports-envelope.avsc
```

If `--output` is omitted, the generated `.avsc` JSON is written to stdout.

The converter reads JSON and YAML OpenAPI files. This example exercises `allOf`
composition, maps, arrays, and `oneOf` unions:

```bash
uv run openapi-get-avro generate \
  --input examples/complex.openapi.yaml \
  --namespace com.example.sports \
  --rootname SportsEnvelope \
  --output build/complex-sports-envelope.avsc
```

Useful policy and naming options:

```bash
uv run openapi-get-avro generate \
  --input examples/complex.openapi.yaml \
  --namespace com.example.sports \
  --rootname SportsEnvelope \
  --name-strategy operationId \
  --include-status-codes 200,206,default \
  --content-type application/json \
  --any-of-policy fail \
  --enum-policy fail \
  --unknown-object-policy fail \
  --output build/sports-envelope.avsc
```

Accepted CLI values:

- `--name-strategy`: `operationId` or `path`
- `--any-of-policy`: `fail` or `union`
- `--enum-policy`: `fail`, `string`, or `sanitize`
- `--unknown-object-policy`: `fail`, `map`, `string`, or `empty-record`
- `--include-status-codes`: comma-separated response codes, evaluated in the order provided

The implemented strict behavior is the default: invalid enum values and ambiguous
free-form objects fail. `--any-of-policy union` is implemented when every branch
maps to a unique named Avro type.

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

## What is included

By default, the generator includes only:

- `GET` operations under `paths`
- status code `200`
- response content type `application/json`

Non-GET methods and non-JSON responses are ignored. Local component refs such as
`#/components/schemas/Team` are resolved. Unsupported remote refs fail with a
project-specific error.

## Troubleshooting

Most conversion failures include the OpenAPI response being converted, for example:

```text
Failed to generate Avro schema for examples/api.yaml: GET /matches/{id} response 200: ...
```

Common causes:

- `Unsupported $ref`: only local `#/components/schemas/...` refs are supported.
- `Invalid Avro enum symbol`: enum values must already be valid Avro symbols in strict mode.
- `Conflicting allOf field`: two `allOf` branches define the same property with different schemas.
- `anyOf`: the default policy is `fail`; use `--any-of-policy union` only when every branch maps to a unique named Avro type.
- Free-form objects such as `{ "type": "object" }` are ambiguous in strict mode.

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
