# Edge cases

## Empty successful response

A `204` response with no content should be skipped by default. If explicitly included in the future, represent it as an empty record with a clear name such as `GetMatch204Response`.

## Multiple success responses

If the user includes multiple response codes, generate one branch per response code unless the schemas are identical and share a stable name. Append the status code to avoid branch-name collisions.

## Duplicate union branches

Avro unions cannot contain duplicate primitive branches and become confusing with duplicate named records. Deduplicate identical named references and fail on ambiguous duplicates.

## Recursive schemas

Recursive component refs must use Avro named references. Do not inline recursively forever.

## Free-form objects

Schemas like this are ambiguous:

```json
{ "type": "object" }
```

Strict mode should fail. A future lenient mode may map to `map<string>` or an empty record, depending on `unknown_object_policy`.

## OpenAPI 3.1 type arrays

OpenAPI 3.1 may express nullability as:

```json
{ "type": ["string", "null"] }
```

This should map to `['null', 'string']` with default null when used as a field.

## Discriminator

OpenAPI discriminators may help name `oneOf` branches, but Avro uses branch type names as the discriminator. MVP does not need special discriminator handling.
