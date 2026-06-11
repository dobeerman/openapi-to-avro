You are implementing this repository as a senior data engineer and Python package maintainer.

This repository is an MVP scaffold for a deterministic OpenAPI GET-response to Avro schema generator.

The project uses:

- `uv` for dependency management and command execution.
- `ruff` for formatting and linting.
- `mypy` for static type checking.
- `pytest` for tests.
- `fastavro` for generated Avro schema validation.

Do not use `pip`, `black`, `isort`, or ad-hoc virtualenv commands. Use `uv run ...` for all Python commands.

## First, read the project context

Read these files before editing code:

- `AGENTS.md`
- `README.md`
- `pyproject.toml`
- `docs/PROJECT_BRIEF.md`
- `docs/TECHNICAL_SPEC.md`
- `docs/AVRO_MAPPING.md`
- `docs/NAMING_AND_DETERMINISM.md`
- `docs/ACCEPTANCE_CRITERIA.md`
- `docs/TOOLING.md`
- `tests/fixtures/minimal.openapi.json`
- `tests/fixtures/expected-minimal.avsc`
- `tests/test_minimal_conversion.py`
- `tests/test_cli_contract.py`
- `tests/test_naming.py`

After reading, briefly summarize the implementation plan in no more than 8 bullets.

## Goal

Implement the first working MVP of the OpenAPI GET to Avro converter.

The MVP must make the existing minimal fixture tests pass without changing the expected fixture unless the fixture is provably inconsistent with the project specification.

## Required behavior

Implement support for:

1. Loading OpenAPI documents from JSON and YAML files.
2. Selecting only `GET` operations from `paths`.
3. Selecting only successful JSON responses.
4. Default response selection:
   - Prefer status code `200`.
   - Use `application/json`.
   - Ignore non-GET methods.
   - Ignore non-JSON responses.
5. Resolving local `$ref` values such as:
   - `#/components/schemas/Match`
   - `#/components/schemas/Venue`
6. Converting OpenAPI object schemas to Avro records.
7. Converting OpenAPI arrays to Avro arrays.
8. Converting OpenAPI primitive types:
   - `string`
   - `boolean`
   - `integer`
   - `number`
9. Converting known string formats:
   - `format: uuid` to Avro string with logical type `uuid`
   - `format: date` to Avro int with logical type `date`
   - `format: date-time` to Avro long with logical type `timestamp-millis`
10. Converting OpenAPI enums to Avro enums when enum values are valid Avro symbols.
11. Handling required and optional fields:
   - Required fields are emitted as their direct Avro type.
   - Optional fields are emitted as `["null", <type>]` with `"default": null`.
12. Handling OpenAPI nullable fields:
   - `nullable: true`
   - `type: ["null", "..."]`, if present
13. Generating the root envelope record with:
   - namespace from CLI `--namespace`
   - name from CLI `--rootname`
   - root doc from OpenAPI `info.description`, falling back to `info.title`, falling back to a generated doc
   - fixed metadata fields already described in the docs/tests
   - a `data` field whose type is an Avro union of all selected GET response records
14. Generating deterministic Avro names:
   - Prefer `operationId`.
   - Fall back to HTTP method plus path.
   - Produce valid PascalCase Avro names.
   - Avoid invalid Avro identifiers.
15. Validating the generated schema with `fastavro.parse_schema`.

## Important Avro rule

Avro does not have a `oneof` keyword.

The root `data` field must use an Avro union, represented as a JSON array:

```json
{
  "name": "data",
  "type": [
    {
      "type": "record",
      "name": "GetMatchResponse",
      "fields": []
    }
  ]
}
````

## Implementation boundaries

Focus only on the MVP.

Do not implement advanced features yet unless needed by the existing tests:

* Do not implement full remote `$ref` support.
* Do not implement Schema Registry integration.
* Do not implement `allOf`/`oneOf`/`anyOf` unless the current tests require it.
* Do not introduce a large framework or plugin system.
* Do not silently sanitize enum values in a way that changes their meaning.
* Do not change the CLI contract unless the tests or docs are internally inconsistent.

If an unsupported feature is encountered, raise a clear project-specific exception from `exceptions.py`.

## Suggested implementation path

1. Inspect existing skeleton files under `src/openapi_get_avro/`.
2. Implement the converter in small, testable functions.
3. Keep the public API simple:

   * the CLI should call the converter
   * the converter should return a Python `dict`
   * the CLI should serialize deterministic JSON
4. Add helper functions only when they make the code easier to test.
5. Preserve deterministic output ordering.
6. Prefer straightforward Python over clever schema metaprogramming.

## Required commands

Before making changes, run the focused tests once to see the current failure state:

```bash
uv sync --locked
uv run --locked pytest tests/test_minimal_conversion.py tests/test_cli_contract.py tests/test_naming.py -q
```

After implementation, run:

```bash
uv run --locked ruff format .
uv run --locked ruff check .
uv run --locked mypy src
uv run --locked pytest tests/test_minimal_conversion.py tests/test_cli_contract.py tests/test_naming.py -q
```

If those pass, run the full test suite:

```bash
uv run --locked pytest -q
```

## Definition of done

The task is complete when:

* `tests/test_minimal_conversion.py` passes.
* `tests/test_cli_contract.py` passes.
* `tests/test_naming.py` passes.
* `uv run --locked ruff format --check .` passes.
* `uv run --locked ruff check .` passes.
* `uv run --locked mypy src` passes.
* The CLI example in `README.md` works.
* Generated Avro output is deterministic across repeated runs.
* Generated Avro parses successfully with `fastavro.parse_schema`.
* Unsupported schema constructs fail with clear project-specific errors.

## Reporting back

When finished, report:

1. Files changed.
2. Main implementation decisions.
3. Commands run and their results.
4. Any known limitations left for the next prompt.

```

After this first task is green, the next prompt should focus only on `$ref` reuse, naming collisions, maps, and nested anonymous records.
