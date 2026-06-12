Add an option to remove configured suffixes from generated Avro named types.

Context:

- Some OpenAPI component schema names include implementation suffixes such as `Dto`.
- The generated Avro schema should be able to emit cleaner named types, for example:

```json
{ "name": "AttributeDto" }
```

should become:

```json
{ "name": "Attribute" }
```

Tasks:

1. Add a CLI option named `--remove-name-suffixes` that accepts a comma-separated list of suffixes to remove from generated Avro named type names.
2. Add the option to `GenerationOptions` with a deterministic default that preserves current behavior when the option is omitted.
3. Apply suffix removal only to generated Avro named types: records, enums, response wrapper records, component refs, and nested/generated record or enum names. Do not mutate Avro field names such as `entity_type`, `venue`, or OpenAPI property names.
4. Remove only exact trailing suffix matches after the source name is converted into the preferred Avro name shape. For example, `AttributeDto` with `Dto` becomes `Attribute`; `AttributeDTO` should only change if `DTO` is configured.
5. Preserve existing required suffixes that the generator adds after the removal step where appropriate. For example, response records should still end in `Response`; enum fallback names should still end in `Enum` when that is how the current code disambiguates enum names.
6. Keep naming deterministic and collision-safe. If suffix removal causes two distinct OpenAPI schemas to prefer the same Avro name, use the existing deterministic numeric suffix allocation behavior.
7. Reject invalid or empty suffix entries with a clear CLI validation error. Keep strict Avro name validation after suffix removal, and fail clearly if the resulting name is empty or invalid.
8. Update `--help` output and README usage examples for the new option.
9. Add focused tests covering:
   - CLI help exposes `--remove-name-suffixes`.
   - Component ref name `AttributeDto` becomes `Attribute` when `--remove-name-suffixes Dto` is provided.
   - Nested/generated names also honor the option.
   - Current output is unchanged when the option is omitted.
   - Collisions after suffix removal are resolved deterministically.
   - Field/property names are not changed.

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```
