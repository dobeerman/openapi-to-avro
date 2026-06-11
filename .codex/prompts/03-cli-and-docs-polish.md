Polish the CLI and docs without changing core semantics.

Tasks:

1. Improve CLI error messages so users can identify the path/schema that failed.
2. Add `--name-strategy`, `--any-of-policy`, `--enum-policy`, and `--unknown-object-policy` options.
3. Ensure `--include-status-codes 200,206,default` works deterministically.
4. Update `README.md` with real examples based on the implemented CLI.
5. Add a short troubleshooting section.

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```
