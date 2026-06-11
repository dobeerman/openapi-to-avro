.PHONY: sync lock test lint lint-fix format format-check typecheck check clean help

help:
	@printf '%s\n' 'Common commands:'
	@printf '%s\n' '  make sync          Install/update the uv-managed project environment'
	@printf '%s\n' '  make lock          Refresh uv.lock without installing packages'
	@printf '%s\n' '  make format        Format Python files with Ruff'
	@printf '%s\n' '  make lint          Lint Python files with Ruff'
	@printf '%s\n' '  make typecheck     Run mypy against src/'
	@printf '%s\n' '  make test          Run pytest'
	@printf '%s\n' '  make check         Run format check, lint, typecheck, and tests'

sync:
	uv sync

lock:
	uv lock

test:
	uv run pytest

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy src

check: format-check lint typecheck test

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
