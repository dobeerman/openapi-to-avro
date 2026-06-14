# OpenAPI to Avro mapping

## Primitive types

| OpenAPI schema | Avro type |
| --- | --- |
| `type: string` | `string` |
| `type: string`, `format: uuid` | `{ "type": "string", "logicalType": "uuid" }` |
| `type: string`, `format: date` | `{ "type": "int", "logicalType": "date" }` |
| `type: string`, `format: date-time` | `{ "type": "long", "logicalType": "timestamp-millis" }` |
| `type: integer`, `format: int32` | `int` |
| `type: integer`, `format: int64` | `long` |
| `type: integer` | `long` |
| `type: number`, `format: float` | `float` |
| `type: number`, `format: double` | `double` |
| `type: number` | `double` |
| `type: boolean` | `boolean` |

When `--enforce-timestamp` is set, string schemas with `format: date`,
`format: date-time`, or `format: timestamp` all map to
`{ "type": "long", "logicalType": "timestamp-millis" }`.

## Objects

OpenAPI object schemas become Avro records.

```json
{
  "type": "object",
  "required": ["id"],
  "properties": {
    "id": { "type": "string" },
    "name": { "type": "string" }
  }
}
```

becomes:

```json
{
  "type": "record",
  "name": "Example",
  "fields": [
    { "name": "id", "type": "string" },
    { "name": "name", "type": ["null", "string"], "default": null }
  ]
}
```

## Arrays

```json
{ "type": "array", "items": { "type": "string" } }
```

becomes:

```json
{ "type": "array", "items": "string" }
```

## Maps

OpenAPI `additionalProperties` maps to Avro maps when it contains a schema:

```json
{
  "type": "object",
  "additionalProperties": { "type": "string" }
}
```

becomes:

```json
{ "type": "map", "values": "string" }
```

Free-form objects are ambiguous. Strict mode should fail unless `unknown_object_policy` says otherwise.

## Enums

String enums become Avro enums only when every value is a valid Avro enum symbol.

```json
{ "type": "string", "enum": ["CREATED", "UPDATED"] }
```

becomes:

```json
{ "type": "enum", "name": "ExampleEnum", "symbols": ["CREATED", "UPDATED"] }
```

Invalid enum values in strict mode must fail. Lenient policies may convert to `string` or sanitize, but sanitization must be documented in the generated field `doc`.

## `allOf`

Treat `allOf` object composition as a flattened record.

Rules:

- Resolve refs first.
- Merge `required` arrays.
- Merge `properties` in branch order.
- If the same field appears with incompatible schemas, fail in strict mode.

## `oneOf`

Map `oneOf` to an Avro union only when each branch can become a unique Avro type.

```json
{
  "oneOf": [
    { "$ref": "#/components/schemas/HomeTeam" },
    { "$ref": "#/components/schemas/AwayTeam" }
  ]
}
```

becomes:

```json
["com.example.HomeTeam", "com.example.AwayTeam"]
```

## `anyOf`

`anyOf` means one or more branches may match. Avro unions select one branch. Default strict policy is to fail. Lenient policy may map to a union with a warning.

## Unsupported JSON Schema keywords for MVP

- `not`
- `patternProperties`
- `dependentSchemas`
- `if`, `then`, `else`
- conditional validation keywords
- arbitrary remote refs
