# Project brief

## Problem

We receive OpenAPI specifications and need to generate one Avro schema suitable for Kafka value serialization. Only GET method paths are relevant. Every selected GET response must become one branch under a root envelope field named `data`.

## Primary user

A data engineer who needs to publish API entity snapshots or read-model payloads into Kafka with a stable Avro contract.

## Output

A single `.avsc` JSON file containing:

- A root Avro record using the user-provided namespace and root name.
- Fixed metadata fields: `id`, `timestamp`, `operation`, `entity_type`.
- A `data` field whose type is an Avro union of named records, one per selected GET response representation.
- Referenced component schemas built into the Avro schema as named records or enums.

## Non-goals for the first release

- Generating schemas for non-GET methods.
- Supporting request bodies or parameters as part of the Avro payload.
- Supporting remote `$ref` URLs.
- Registering schemas in Confluent Schema Registry.
- Generating source code from Avro.

## Tooling principle

The repository uses `uv` for dependency management and `ruff` for formatting/linting so Codex, CI, and local development share the same command surface.

## Important design principle

The generator should behave like a compiler. It should produce deterministic output or fail with a useful error. It should not produce pleasant-looking but semantically unsafe schemas.
