Continue from the MVP implementation.

Focus only on reference resolution and Avro naming hardening.

Read:

- `docs/NAMING_AND_DETERMINISM.md`
- `docs/EDGE_CASES.md`
- `tests/test_naming.py`

Tasks:

1. Ensure every generated record and enum has a valid Avro name.
2. Deduplicate names deterministically with numeric suffixes only when necessary.
3. Reuse named component schemas by full Avro name instead of duplicating equivalent records.
4. Detect unsupported external refs and raise a clear error.
5. Add or update tests for path fallback naming, duplicate operation IDs, and invalid enum symbols.

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest tests/test_naming.py tests/test_minimal_conversion.py
```
