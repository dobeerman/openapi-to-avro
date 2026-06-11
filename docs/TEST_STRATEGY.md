# Test strategy

## Test layers

1. Unit tests for name conversion.
2. Unit tests for primitive type mapping.
3. Unit tests for `$ref` resolution.
4. Fixture tests for full OpenAPI to Avro conversion.
5. CLI tests using `typer.testing.CliRunner`.
6. Avro validity tests using `fastavro.parse_schema`.

## Golden fixtures

Golden expected `.avsc` files are allowed because deterministic JSON output is part of the product contract.

Rules for golden fixtures:

- Keep them small.
- Use realistic OpenAPI features.
- Do not update them just to make tests pass. Update only when the spec changes.

## Local verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

## Minimum acceptance tests

- Non-GET operations are ignored.
- Required fields are non-null.
- Optional fields are nullable with default null.
- `$ref` is resolved into built-in named Avro records.
- UUID and date-time formats become Avro logical types.
- Generated Avro parses with `fastavro.parse_schema`.
- Repeated runs generate identical JSON.
