Implement composition support.

Read:

- `docs/AVRO_MAPPING.md`
- `docs/EDGE_CASES.md`
- `examples/complex.openapi.yaml`

Tasks:

1. Implement `allOf` flattening for object schemas.
2. Implement `oneOf` as Avro unions when each branch maps to a unique named type.
3. Implement `anyOf` according to `GenerationOptions.any_of_policy`.
4. Detect conflicting `allOf` fields and fail in strict mode.
5. Add tests for the complex fixture.

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```
