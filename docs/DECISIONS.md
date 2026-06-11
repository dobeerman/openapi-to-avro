# Architecture decisions

## ADR-001: Use Python for the CLI

Python is suitable for a data engineering utility, has mature OpenAPI/YAML tooling, and integrates cleanly into CI jobs.

## ADR-002: Use Avro union for `data`

Avro has no `oneof` keyword. A union is represented as a JSON array. Therefore, the root `data` field uses an Avro union containing one named record per selected GET response.

## ADR-003: Strict mode by default

OpenAPI and Avro have different semantics. Strict mode prevents lossy mappings from silently entering Kafka contracts.

## ADR-004: Golden fixtures are acceptable

Deterministic output is a contract. Golden `.avsc` fixtures provide a clear safety net for refactors.

## ADR-005: Use uv for project environments

The project uses `uv` as the single dependency and command runner. This keeps Codex, local development, and CI on the same locked dependency graph.

## ADR-006: Use Ruff as the single Python style tool

Ruff handles formatting, import sorting, linting, and safe fixes. The project should not add overlapping style tools unless this decision is revisited.
