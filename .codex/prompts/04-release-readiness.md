Prepare the project for first internal release.

Tasks:

1. Run the full check suite through `make check`, which wraps `uv run` commands.
2. Review generated schemas for Avro validity with `fastavro.parse_schema`.
3. Add changelog section for version `0.1.0`.
4. Add examples showing expected behavior for ignored non-GET operations and skipped non-JSON responses.
5. Review `AGENTS.md` and update it only with rules that prevented real mistakes during implementation. Preserve the uv and Ruff workflow rules.

Run:

```bash
make check
```

Return a concise release note with remaining known limitations.
