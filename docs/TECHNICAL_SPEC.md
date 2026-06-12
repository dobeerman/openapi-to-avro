# Technical specification

## CLI contract

Required options:

```text
--input       Path to OpenAPI JSON/YAML file
--namespace   Avro namespace for generated named types
--rootname    Avro root record name
```

Optional options:

```text
--output                  Output path. If omitted, write to stdout.
--include-status-codes    Comma-separated response codes. Default: 200.
--content-type            Response content type. Default: application/json.
--strict / --lenient      Strict mode fails on ambiguous constructs. Default: strict.
--name-strategy           operationId or path. Default: operationId.
--field-name-case         preserve, snake_case, camelCase, or PascalCase. Default: preserve.
--any-of-policy           fail or union. Default: fail.
--enum-policy             fail, string, or sanitize. Default: fail.
--unknown-object-policy   fail, map, string, or empty-record. Default: fail.
--remove-name-suffixes    Comma-separated generated named-type suffixes to remove. Default: none.
--references-output-dir   Also write Confluent Schema Registry referenced schemas to this directory.
--references-manifest-output
                          Manifest path for referenced schemas. Default: <references-output-dir>/manifest.json.
--reference-subject-template
                          Subject template. Supports {fullname}, {namespace}, {name}, and {rootname}. Default: {fullname}.
--root-subject            Schema Registry subject for the root envelope. For Confluent TopicNameStrategy
                          topic values, use <topic>-value.
```

## OpenAPI selection rules

1. Walk `paths` in deterministic sorted order.
2. Select only method key `get`, case-insensitive.
3. For each selected operation, inspect `responses`.
4. Include configured status codes only. Default is `200`.
5. For each included status code, include configured response content type only. Default is `application/json`.
6. If no matching response schema exists for a GET operation, skip it with an internal warning or fail in strict mode. MVP may skip.
7. Ignore non-GET operations completely.

## Root envelope

The root schema must use:

```json
{
  "type": "record",
  "namespace": "<namespace>",
  "name": "<rootname>",
  "doc": "<info.description or info.title or generated fallback>",
  "fields": [
    { "name": "id", "type": { "type": "string", "logicalType": "uuid" } },
    { "name": "timestamp", "type": { "type": "long", "logicalType": "timestamp-millis" } },
    { "name": "operation", "type": { "type": "enum", "name": "Operation", "symbols": ["CREATED", "UPDATED", "DELETED"] } },
    { "name": "entity_type", "type": { "type": "enum", "name": "EntityType", "symbols": [] } },
    { "name": "data", "type": [] }
  ]
}
```

`entity_type.symbols` should be derived from selected GET operation tags when available. Use the first tag. If there is no tag, derive from the response record name. Symbols must be valid Avro enum symbols. In strict mode, invalid derived symbols should fail with a clear error.

## Response branch naming

Preferred name source:

```text
operationId -> PascalCase(operationId) + Response
```

Fallback:

```text
GET /matches/{matchId}/lineups -> GetMatchesByMatchIdLineupsResponse
```

If multiple status codes are included for the same operation, append status:

```text
GetMatch200Response
GetMatch206Response
```

## Reference handling

Supported refs:

```text
#/components/schemas/<Name>
```

The converter must maintain a registry:

```text
OpenAPI ref -> Avro full name
Avro full name -> schema definition
```

This is required to avoid duplicate records and to handle recursion safely.

Unsupported refs:

- Remote URLs.
- File refs.
- JSON Pointer refs outside `components.schemas` for MVP.

In strict mode, unsupported refs must fail.

## Field requiredness and nullability

OpenAPI fields are optional unless listed in the parent object's `required` array.

Required, non-null field:

```json
{ "name": "id", "type": "string" }
```

Optional field:

```json
{ "name": "description", "type": ["null", "string"], "default": null }
```

Nullable required field:

```json
{ "name": "name", "type": ["null", "string"], "default": null }
```

For Avro compatibility, `null` must be first when the default is null.

## Determinism

The same input and options must produce byte-for-byte identical output.

Rules:

- Sort OpenAPI paths lexicographically.
- Sort methods only as needed. Only GET is selected.
- Preserve property order from OpenAPI objects.
- Sort selected response status codes according to the order in `--include-status-codes`.
- Use stable generated names.
- Use `json.dumps(..., indent=2)` for output.

When `--remove-name-suffixes` is configured, remove exact trailing suffix matches
from generated Avro named types after converting the source text to Avro name
shape. Do not mutate field/property names.

When `--field-name-case` is configured, transform OpenAPI response payload field
names to the selected case after reading requiredness from the original OpenAPI
property names. Do not mutate generated record names or enum names. The fixed
root envelope fields remain unchanged.

## Validation

After generating the schema, validate it with `fastavro.parse_schema`.

Validation failures should include enough context to identify the generated type that failed.

## Confluent Schema Registry references

When `--references-output-dir` is set, the CLI must still write the bundled
self-contained schema to `--output` or stdout. It also writes one standalone
schema file per generated Avro named type and a manifest describing Confluent
Schema Registry registration metadata.

Referenced-schema files must use fully qualified Avro names for dependencies.
Reference subjects are formatted with `--reference-subject-template`. The root
envelope subject may be overridden independently with `--root-subject`, which is
the expected option for Confluent's default topic value subject, `<topic>-value`.
The manifest must be deterministic and ordered so dependency subjects appear
before schemas that reference them:

```text
shared leaf named types
-> named types that depend on them
-> GET response records
-> root envelope schema
```

Manifest entries include:

```json
{
  "fullname": "com.example.GetMatchResponse",
  "subject": "com.example.GetMatchResponse",
  "file": "com.example.GetMatchResponse.avsc",
  "references": [
    {
      "name": "com.example.Venue",
      "subject": "com.example.Venue",
      "version": "latest"
    }
  ]
}
```
