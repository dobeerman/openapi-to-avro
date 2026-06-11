# Acceptance criteria

## MVP acceptance

The project is acceptable for first internal use when:

- `uv sync` creates the local project environment from `pyproject.toml` and `uv.lock`.
- `uv run ruff format --check .` passes.
- `uv run ruff check .` passes.
- `openapi-get-avro --help` works.
- The CLI can load JSON and YAML OpenAPI files.
- Only GET methods are included.
- Non-GET methods are ignored.
- The root schema uses the requested namespace and root name.
- The `data` field is an Avro union of named records.
- Local component `$ref` values are resolved.
- Required and optional OpenAPI fields map correctly to Avro nullability.
- UUID, date, and date-time map to Avro logical types.
- Enums with valid symbols become Avro enums.
- Invalid enum symbols fail in strict mode.
- Output is deterministic.
- Generated schemas validate with `fastavro.parse_schema`.
- The test suite passes.

## Done means

A Codex task is not done until it has run the relevant `uv run ...` checks and reported which commands passed or failed.
