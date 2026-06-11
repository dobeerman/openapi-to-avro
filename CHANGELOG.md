# Changelog

## 0.1.0 - 2026-06-11

- Added the first working OpenAPI GET-response to Avro envelope converter.
- Added JSON and YAML OpenAPI loading through the `openapi-get-avro generate` CLI.
- Included only configured successful `GET` responses with `application/json` content by default.
- Added local component `$ref` resolution, deterministic Avro naming, name deduplication, and component reuse.
- Added object, array, primitive, logical type, enum, optional field, and nullable field mappings.
- Added `allOf` flattening, `oneOf` Avro unions, and policy-controlled `anyOf` unions.
- Added CLI policy options for naming, `anyOf`, enum handling, unknown objects, content type, and status codes.
- Added generated-schema validation with `fastavro.parse_schema`.
- Added examples for minimal conversion, composition, ignored non-GET operations, and skipped non-JSON responses.
- Standardized local development on `uv`, Ruff, mypy, and pytest through `make check`.
