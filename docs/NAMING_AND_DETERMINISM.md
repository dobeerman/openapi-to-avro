# Naming and determinism

## Avro name rules

Avro names must start with `[A-Za-z_]` and continue with `[A-Za-z0-9_]`.

## Record naming strategy

Use `operationId` first:

```text
getMatch -> GetMatchResponse
```

If missing, derive from path:

```text
GET /matches/{matchId}/lineups -> GetMatchesByMatchIdLineupsResponse
```

Rules:

1. Split on non-alphanumeric boundaries.
2. For path parameters, prefix with `By`.
3. PascalCase each segment.
4. Prefix names starting with a digit using `N` or a configured prefix.
5. Append `Response` for top-level response records.

## Nested anonymous object names

Derive from parent and field:

```text
GetMatchResponse.venue -> GetMatchResponseVenue
GetMatchResponse.participants[] -> GetMatchResponseParticipantsItem
```

## Field name case

By default, OpenAPI response payload field names are preserved. With
`--field-name-case`, payload fields can be emitted as `snake_case`, `camelCase`,
or `PascalCase`. This does not change record names, enum names, enum symbols, or
the fixed root envelope fields.

If two source properties transform to the same Avro field name, generation fails
instead of silently dropping or merging a field.

## Deduplication

If two generated names collide but refer to different schemas, append deterministic suffixes:

```text
GetMatchResponse
GetMatchResponse2
GetMatchResponse3
```

If they refer to the same component ref, reuse the existing full name.

## JSON output stability

Use consistent JSON formatting:

```python
json.dumps(schema, indent=2, ensure_ascii=False)
```

Do not include generation timestamps in schema output.
