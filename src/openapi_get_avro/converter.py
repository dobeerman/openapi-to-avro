"""Conversion entry point for OpenAPI GET responses to Avro envelopes."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any

from fastavro import parse_schema

from .exceptions import (
    AvroNameError,
    InvalidOpenApiError,
    OpenApiAvroError,
    UnsupportedSchemaError,
)
from .models import (
    GenerationOptions,
    ReferencedSchemaArtifact,
    ReferencedSchemaSet,
    SchemaRegistryReference,
    SelectedOperation,
)

AVRO_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOCAL_COMPONENT_REF_PREFIX = "#/components/schemas/"
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}

JsonDict = dict[str, Any]
NameIdentity = tuple[Hashable, ...]
PRIMITIVE_AVRO_TYPES = {
    "null",
    "boolean",
    "int",
    "long",
    "float",
    "double",
    "bytes",
    "string",
}


class _Converter:
    def __init__(self, openapi_doc: JsonDict, options: GenerationOptions) -> None:
        self.openapi_doc = openapi_doc
        self.options = options
        self.components = self._components()
        self.allocated_names: dict[str, NameIdentity] = {
            options.root_name: ("root",),
            "Operation": ("envelope", "operation"),
            "EntityType": ("envelope", "entity_type"),
        }
        self.ref_names: dict[str, str] = {}
        self.refs_in_progress: set[str] = set()

    def convert(self) -> JsonDict:
        selected = self._filter_operations(self._select_operations())
        data_types: list[Any] = []
        entity_symbols: list[str] = []

        for operation in selected:
            try:
                response_identity = self._response_identity(operation)
                record_name = self._response_record_name(operation)
                response_doc = self._response_doc(operation)
                data_types.append(
                    self._response_schema_to_avro(
                        operation.schema,
                        record_name,
                        record_doc=response_doc,
                        name_identity=response_identity,
                    )
                )
                symbol_source = self._first_tag(operation) or record_name
                symbol = self._enum_symbol_from_text(symbol_source)
            except OpenApiAvroError as exc:
                raise type(exc)(
                    f"GET {operation.path} response {operation.status_code}: {exc}"
                ) from exc
            if symbol not in entity_symbols:
                entity_symbols.append(symbol)

        schema: JsonDict = {
            "type": "record",
            "namespace": self.options.namespace,
            "name": self._sanitize_avro_name(self.options.root_name, "root record name"),
            "doc": self._root_doc(),
            "fields": [
                {
                    "name": "id",
                    "type": {"type": "string", "logicalType": "uuid"},
                },
                {
                    "name": "timestamp",
                    "type": {"type": "long", "logicalType": "timestamp-millis"},
                },
                {
                    "name": "operation",
                    "type": {
                        "type": "enum",
                        "name": "Operation",
                        "symbols": ["CREATED", "UPDATED", "DELETED"],
                    },
                },
                {
                    "name": "entity_type",
                    "type": {
                        "type": "enum",
                        "name": "EntityType",
                        "symbols": entity_symbols,
                    },
                },
                {
                    "name": "data",
                    "type": data_types,
                },
            ],
        }
        self._validate_avro(schema)
        return schema

    def _filter_operations(self, operations: list[SelectedOperation]) -> list[SelectedOperation]:
        if not self.options.include_response_records:
            return operations

        matched_selectors: set[str] = set()
        filtered: list[SelectedOperation] = []
        for operation in operations:
            response_name = self._response_record_preferred_name(operation)
            response_selectors = self._response_record_selectors(operation, response_name)
            selectors = [
                selector
                for selector in self.options.include_response_records
                if selector in response_selectors
            ]
            if not selectors:
                continue
            matched_selectors.update(selectors)
            filtered.append(operation)

        unmatched = [
            selector
            for selector in self.options.include_response_records
            if selector not in matched_selectors
        ]
        if unmatched:
            formatted = ", ".join(repr(selector) for selector in unmatched)
            raise InvalidOpenApiError(
                f"--include-response-records did not match generated response records: {formatted}"
            )
        return filtered

    def _response_record_selectors(
        self, operation: SelectedOperation, response_name: str
    ) -> set[str]:
        selectors = {response_name}
        if not response_name.endswith("Response"):
            return selectors

        stem = response_name.removesuffix("Response")
        selectors.add(stem)

        status_suffix = self._status_suffix(operation.status_code)
        if stem.endswith(status_suffix):
            stem = stem[: -len(status_suffix)]
            selectors.add(stem)

        if stem.startswith("Get"):
            stem = stem.removeprefix("Get")
            selectors.add(stem)
        if stem.startswith("Api"):
            selectors.add(stem.removeprefix("Api"))
        return selectors

    def _components(self) -> JsonDict:
        components = self.openapi_doc.get("components", {})
        if not isinstance(components, dict):
            raise InvalidOpenApiError("OpenAPI components must be an object")
        schemas = components.get("schemas", {})
        if not isinstance(schemas, dict):
            raise InvalidOpenApiError("OpenAPI components.schemas must be an object")
        return schemas

    def _select_operations(self) -> list[SelectedOperation]:
        paths = self.openapi_doc.get("paths")
        if not isinstance(paths, dict):
            raise InvalidOpenApiError("OpenAPI paths must be an object")

        selected: list[SelectedOperation] = []
        for path in sorted(paths):
            path_item = paths[path]
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if not isinstance(method, str) or method.lower() not in HTTP_METHODS:
                    continue
                if method.lower() != "get":
                    continue
                if not isinstance(operation, dict):
                    raise InvalidOpenApiError(f"GET operation for {path} must be an object")
                selected.extend(self._select_responses(path, operation))
        return selected

    def _response_schema_to_avro(
        self,
        schema: JsonDict,
        name_hint: str,
        *,
        record_doc: str,
        name_identity: NameIdentity,
    ) -> JsonDict:
        avro_type = self._schema_to_avro(
            schema,
            name_hint,
            record_doc=record_doc,
            name_identity=name_identity,
        )
        if isinstance(avro_type, dict) and avro_type.get("type") == "record":
            return avro_type

        record_name = self._allocate_name(name_hint, name_identity)
        return {
            "type": "record",
            "name": record_name,
            "doc": record_doc,
            "fields": [
                {
                    "name": "items",
                    "type": avro_type,
                }
            ],
        }

    def _select_responses(self, path: str, operation: JsonDict) -> list[SelectedOperation]:
        responses = operation.get("responses")
        if not isinstance(responses, dict):
            raise InvalidOpenApiError(f"GET {path} responses must be an object")

        selected: list[SelectedOperation] = []
        for status_code in self.options.include_status_codes:
            response = responses.get(status_code)
            if response is None:
                continue
            if not isinstance(response, dict):
                raise InvalidOpenApiError(f"GET {path} response {status_code} must be an object")
            content = response.get("content")
            if not isinstance(content, dict):
                continue
            media_type = content.get(self.options.content_type)
            if not isinstance(media_type, dict):
                continue
            schema = media_type.get("schema")
            if not isinstance(schema, dict):
                continue
            operation_id = operation.get("operationId")
            if operation_id is not None and not isinstance(operation_id, str):
                raise InvalidOpenApiError(f"GET {path} operationId must be a string")
            description = response.get("description")
            if description is not None and not isinstance(description, str):
                raise InvalidOpenApiError(f"GET {path} response description must be a string")
            selected.append(
                SelectedOperation(
                    path=path,
                    method="get",
                    operation_id=operation_id,
                    status_code=status_code,
                    response_description=description,
                    schema=schema,
                )
            )
        return selected

    def _schema_to_avro(
        self,
        schema: JsonDict,
        name_hint: str,
        *,
        record_doc: str | None = None,
        name_identity: NameIdentity | None = None,
    ) -> Any:
        if "$ref" in schema and record_doc is None:
            return self._component_ref_to_avro(schema)
        schema = self._resolve_ref(schema)

        nullable = self._is_nullable(schema)
        if nullable:
            non_null_schema = dict(schema)
            non_null_schema["nullable"] = False
            if isinstance(non_null_schema.get("type"), list):
                non_null_schema["type"] = [
                    item for item in non_null_schema["type"] if item != "null"
                ]
            return self._prepend_null(
                self._schema_to_avro(
                    non_null_schema,
                    name_hint,
                    record_doc=record_doc,
                    name_identity=name_identity,
                )
            )
        if "allOf" in schema:
            schema = self._flatten_all_of(schema, name_hint)
        if "oneOf" in schema:
            return self._composition_union_to_avro(schema["oneOf"], name_hint, keyword="oneOf")
        if "anyOf" in schema:
            if self.options.any_of_policy == "fail":
                raise UnsupportedSchemaError(
                    f"Unsupported schema keyword 'anyOf' in {name_hint}; "
                    "set any_of_policy='union' to map it to an Avro union"
                )
            return self._composition_union_to_avro(schema["anyOf"], name_hint, keyword="anyOf")

        self._reject_unsupported(schema)
        schema_type = self._schema_type(schema)

        enum_values = schema.get("enum")
        if enum_values is not None:
            return self._enum_to_avro(enum_values, name_hint, name_identity=name_identity)

        if schema_type is None and "properties" not in schema:
            raise UnsupportedSchemaError(f"Schema {name_hint} does not define a supported type")
        return self._typed_schema_to_avro(
            schema,
            schema_type,
            name_hint,
            record_doc=record_doc,
            name_identity=name_identity,
        )

    def _typed_schema_to_avro(
        self,
        schema: JsonDict,
        schema_type: str | None,
        name_hint: str,
        *,
        record_doc: str | None,
        name_identity: NameIdentity | None,
    ) -> Any:
        if schema_type == "object" or "properties" in schema:
            avro_type: Any = self._object_to_avro(
                schema,
                name_hint,
                record_doc=record_doc,
                name_identity=name_identity,
            )
        elif schema_type == "array":
            items = schema.get("items")
            if not isinstance(items, dict):
                raise UnsupportedSchemaError(f"Array schema {name_hint} must define object items")
            avro_type = {
                "type": "array",
                "items": self._schema_to_avro(items, f"{name_hint}Item"),
            }
        elif schema_type == "string":
            avro_type = self._string_to_avro(schema)
        elif schema_type == "boolean":
            avro_type = "boolean"
        elif schema_type == "integer":
            avro_type = self._integer_to_avro(schema)
        elif schema_type == "number":
            avro_type = self._number_to_avro(schema)
        else:
            raise UnsupportedSchemaError(
                f"Unsupported OpenAPI type {schema_type!r} in schema {name_hint}"
            )
        return avro_type

    def _object_to_avro(
        self,
        schema: JsonDict,
        name_hint: str,
        *,
        record_doc: str | None = None,
        name_identity: NameIdentity | None = None,
    ) -> JsonDict:
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise UnsupportedSchemaError(f"Object schema {name_hint} properties must be an object")
        additional_properties = schema.get("additionalProperties")
        if not properties and additional_properties is not None:
            if isinstance(additional_properties, dict):
                return {
                    "type": "map",
                    "values": self._schema_to_avro(additional_properties, f"{name_hint}Value"),
                }
            raise UnsupportedSchemaError(
                f"Free-form object schema {name_hint} is unsupported in strict mode"
            )
        if (
            not properties
            and additional_properties is None
            and self.options.unknown_object_policy == "fail"
        ):
            raise UnsupportedSchemaError(f"Object schema {name_hint} has no properties")

        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise InvalidOpenApiError(f"Object schema {name_hint} required must be a string array")
        required_names = set(required)

        fields: list[JsonDict] = []
        avro_field_names: set[str] = set()
        for field_name, field_schema in properties.items():
            fields.append(
                self._property_to_field(
                    field_name,
                    field_schema,
                    name_hint=name_hint,
                    required_names=required_names,
                    avro_field_names=avro_field_names,
                )
            )

        record_name = self._record_name(name_hint, name_identity, schema)
        record: JsonDict = {"type": "record", "name": record_name}
        doc = record_doc if record_doc is not None else schema.get("description")
        if isinstance(doc, str):
            record["doc"] = doc
        record["fields"] = fields
        return record

    def _property_to_field(
        self,
        field_name: Any,
        field_schema: Any,
        *,
        name_hint: str,
        required_names: set[str],
        avro_field_names: set[str],
    ) -> JsonDict:
        if not isinstance(field_name, str):
            raise InvalidOpenApiError(f"Object schema {name_hint} has a non-string field name")
        avro_field_name = self._field_name(field_name, name_hint)
        if avro_field_name in avro_field_names:
            raise AvroNameError(
                f"Field name transform produced duplicate Avro field "
                f"{name_hint}.{avro_field_name!r}"
            )
        avro_field_names.add(avro_field_name)
        if not isinstance(field_schema, dict):
            raise UnsupportedSchemaError(f"Field schema {name_hint}.{field_name} must be an object")

        avro_type = self._schema_to_avro(field_schema, f"{name_hint}{self._pascal(field_name)}")
        nullable = field_name not in required_names
        if nullable and not self._is_null_union(avro_type):
            avro_type = self._prepend_null(avro_type)

        field: JsonDict = {"name": avro_field_name, "type": avro_type}
        if self._is_null_union(avro_type):
            field["default"] = None
        description = field_schema.get("description")
        if isinstance(description, str):
            field["doc"] = description
        return field

    def _record_name(
        self, name_hint: str, name_identity: NameIdentity | None, schema: JsonDict
    ) -> str:
        if name_identity is not None:
            return self._allocate_name(name_hint, name_identity)
        return self._allocate_name(
            self._named_type_base(name_hint, "record name"),
            ("record", self._schema_fingerprint(schema)),
        )

    def _flatten_all_of(self, schema: JsonDict, name_hint: str) -> JsonDict:
        branches = schema.get("allOf")
        if not isinstance(branches, list) or not branches:
            raise UnsupportedSchemaError(f"Schema {name_hint} allOf must be a non-empty array")

        merged_required: list[str] = []
        merged_properties: JsonDict = {}
        for index, branch in enumerate(branches):
            branch_properties, branch_required = self._all_of_branch_parts(branch, name_hint, index)
            for required_field in branch_required:
                if required_field not in merged_required:
                    merged_required.append(required_field)
            for field_name, field_schema in branch_properties.items():
                self._merge_all_of_property(merged_properties, field_name, field_schema, name_hint)

        merged: JsonDict = {"type": "object", "properties": merged_properties}
        if merged_required:
            merged["required"] = merged_required
        description = schema.get("description")
        if isinstance(description, str):
            merged["description"] = description
        return merged

    def _all_of_branch_parts(
        self, branch: Any, name_hint: str, index: int
    ) -> tuple[JsonDict, list[str]]:
        if not isinstance(branch, dict):
            raise UnsupportedSchemaError(
                f"Schema {name_hint} allOf branch {index} must be an object"
            )
        resolved_branch = self._resolve_ref(branch)
        if "allOf" in resolved_branch:
            resolved_branch = self._flatten_all_of(resolved_branch, f"{name_hint}AllOf{index}")
        if "oneOf" in resolved_branch or "anyOf" in resolved_branch:
            raise UnsupportedSchemaError(
                f"Schema {name_hint} allOf branch {index} cannot contain oneOf/anyOf"
            )

        branch_type = self._schema_type(resolved_branch)
        if branch_type not in {None, "object"} and "properties" not in resolved_branch:
            raise UnsupportedSchemaError(
                f"Schema {name_hint} allOf branch {index} must be an object schema"
            )
        branch_properties = resolved_branch.get("properties", {})
        if not isinstance(branch_properties, dict):
            raise UnsupportedSchemaError(
                f"Schema {name_hint} allOf branch {index} properties must be an object"
            )
        branch_required = resolved_branch.get("required", [])
        if not isinstance(branch_required, list) or not all(
            isinstance(item, str) for item in branch_required
        ):
            raise InvalidOpenApiError(
                f"Schema {name_hint} allOf branch {index} required must be a string array"
            )
        return branch_properties, branch_required

    def _merge_all_of_property(
        self, merged_properties: JsonDict, field_name: str, field_schema: Any, name_hint: str
    ) -> None:
        if not isinstance(field_name, str) or not isinstance(field_schema, dict):
            raise UnsupportedSchemaError(
                f"Schema {name_hint} allOf branch properties must map to schemas"
            )
        existing_schema = merged_properties.get(field_name)
        if existing_schema is not None and self._schema_fingerprint(
            existing_schema
        ) != self._schema_fingerprint(field_schema):
            raise UnsupportedSchemaError(
                f"Conflicting allOf field {field_name!r} in schema {name_hint}"
            )
        merged_properties[field_name] = field_schema

    def _composition_union_to_avro(
        self, branches: Any, name_hint: str, *, keyword: str
    ) -> list[Any]:
        if not isinstance(branches, list) or not branches:
            raise UnsupportedSchemaError(f"Schema {name_hint} {keyword} must be a non-empty array")

        avro_types: list[Any] = []
        seen_names: set[str] = set()
        for index, branch in enumerate(branches):
            if not isinstance(branch, dict):
                raise UnsupportedSchemaError(
                    f"Schema {name_hint} {keyword} branch {index} must be an object"
                )
            avro_type = self._schema_to_avro(
                branch, f"{name_hint}{self._pascal(keyword)}{index + 1}"
            )
            branch_name = self._named_type_name(avro_type)
            if branch_name is None:
                raise UnsupportedSchemaError(
                    f"Schema {name_hint} {keyword} branch {index} does not map to a named Avro type"
                )
            if branch_name in seen_names:
                raise UnsupportedSchemaError(
                    f"Schema {name_hint} {keyword} contains duplicate branch {branch_name!r}"
                )
            seen_names.add(branch_name)
            avro_types.append(avro_type)
        return avro_types

    def _named_type_name(self, avro_type: Any) -> str | None:
        if isinstance(avro_type, str) and avro_type not in {
            "null",
            "boolean",
            "int",
            "long",
            "float",
            "double",
            "bytes",
            "string",
        }:
            return avro_type
        if isinstance(avro_type, dict) and avro_type.get("type") in {"record", "enum", "fixed"}:
            name = avro_type.get("name")
            if isinstance(name, str):
                return name
        return None

    def _component_ref_to_avro(self, schema: JsonDict) -> Any:
        ref = self._ref_value(schema)
        if ref in self.ref_names:
            return self.ref_names[ref]

        component_name = self._ref_name(schema)
        allocated_name = self._allocate_name(
            self._named_type_base(component_name, "component ref name"),
            ("component-ref", ref),
        )
        self.ref_names[ref] = allocated_name
        if ref in self.refs_in_progress:
            return allocated_name

        self.refs_in_progress.add(ref)
        try:
            resolved = self._resolve_ref(schema)
            return self._schema_to_avro(
                resolved,
                allocated_name,
                name_identity=("component-ref", ref),
            )
        finally:
            self.refs_in_progress.remove(ref)

    def _resolve_ref(self, schema: JsonDict) -> JsonDict:
        ref = schema.get("$ref")
        if ref is None:
            return schema
        ref = self._ref_value(schema)
        name = ref.removeprefix(LOCAL_COMPONENT_REF_PREFIX)
        resolved = self.components.get(name)
        if not isinstance(resolved, dict):
            raise InvalidOpenApiError(f"Unresolvable local component ref {ref!r}")
        return resolved

    def _ref_name(self, schema: JsonDict) -> str:
        return self._ref_value(schema).removeprefix(LOCAL_COMPONENT_REF_PREFIX)

    def _ref_value(self, schema: JsonDict) -> str:
        ref = schema.get("$ref")
        if not isinstance(ref, str):
            raise InvalidOpenApiError("$ref must be a string")
        if not ref.startswith(LOCAL_COMPONENT_REF_PREFIX):
            raise UnsupportedSchemaError(
                f"Unsupported $ref {ref!r}; only local component refs are supported"
            )
        return ref

    def _reject_unsupported(self, schema: JsonDict) -> None:
        for keyword in (
            "not",
            "patternProperties",
            "dependentSchemas",
            "if",
            "then",
            "else",
        ):
            if keyword in schema:
                raise UnsupportedSchemaError(
                    f"Unsupported schema keyword {keyword!r} in MVP converter"
                )

    def _enum_to_avro(
        self, enum_values: Any, name_hint: str, *, name_identity: NameIdentity | None = None
    ) -> JsonDict:
        if not isinstance(enum_values, list) or not all(
            isinstance(value, str) for value in enum_values
        ):
            raise UnsupportedSchemaError(f"Enum schema {name_hint} must contain string values")
        symbols = [self._require_enum_symbol(value, f"enum {name_hint}") for value in enum_values]
        if name_identity is not None:
            enum_name = self._allocate_name(name_hint, name_identity)
        else:
            enum_name = self._allocate_name(
                f"{self._named_type_base(name_hint, 'enum name')}Enum", ("enum", tuple(symbols))
            )
        return {
            "type": "enum",
            "name": enum_name,
            "symbols": symbols,
        }

    def _string_to_avro(self, schema: JsonDict) -> Any:
        match schema.get("format"):
            case "uuid":
                return {"type": "string", "logicalType": "uuid"}
            case "date":
                return {"type": "int", "logicalType": "date"}
            case "date-time":
                if self.options.timestamp_logical_type == "string":
                    return "string"
                return {"type": "long", "logicalType": "timestamp-millis"}
            case _:
                return "string"

    def _integer_to_avro(self, schema: JsonDict) -> str:
        if schema.get("format") == "int32":
            return "int"
        return "long"

    def _number_to_avro(self, schema: JsonDict) -> str:
        if schema.get("format") == "float":
            return "float"
        return "double"

    def _schema_type(self, schema: JsonDict) -> str | None:
        schema_type = schema.get("type")
        if schema_type is None:
            return None
        if isinstance(schema_type, str):
            return schema_type
        if isinstance(schema_type, list):
            non_null_types = [item for item in schema_type if item != "null"]
            if len(non_null_types) == 1 and isinstance(non_null_types[0], str):
                return non_null_types[0]
        raise UnsupportedSchemaError(f"Unsupported schema type declaration {schema_type!r}")

    def _is_nullable(self, schema: JsonDict) -> bool:
        schema_type = schema.get("type")
        return schema.get("nullable") is True or (
            isinstance(schema_type, list) and "null" in schema_type
        )

    def _is_null_union(self, avro_type: Any) -> bool:
        return isinstance(avro_type, list) and bool(avro_type) and avro_type[0] == "null"

    def _prepend_null(self, avro_type: Any) -> list[Any]:
        if isinstance(avro_type, list):
            return ["null", *(item for item in avro_type if item != "null")]
        return ["null", avro_type]

    def _root_doc(self) -> str:
        info = self.openapi_doc.get("info", {})
        if isinstance(info, dict):
            description = info.get("description")
            if isinstance(description, str) and description:
                return description
            title = info.get("title")
            if isinstance(title, str) and title:
                return title
        return "Generated from OpenAPI GET responses"

    def _response_doc(self, operation: SelectedOperation) -> str:
        doc = f"GET {operation.path} {operation.status_code} response."
        if operation.response_description:
            doc = f"{doc} {operation.response_description}"
        return doc

    def _first_tag(self, operation: SelectedOperation) -> str | None:
        path_item = self.openapi_doc.get("paths", {}).get(operation.path, {})
        if not isinstance(path_item, dict):
            return None
        get_operation = path_item.get("get", {})
        if not isinstance(get_operation, dict):
            return None
        tags = get_operation.get("tags", [])
        if isinstance(tags, list) and tags and isinstance(tags[0], str):
            return tags[0]
        return None

    def _response_record_name(self, operation: SelectedOperation) -> str:
        return self._allocate_name(
            self._response_record_preferred_name(operation),
            self._response_identity(operation),
        )

    def _response_record_preferred_name(self, operation: SelectedOperation) -> str:
        if self.options.name_strategy == "operationId" and operation.operation_id:
            base = self._named_type_base(operation.operation_id, "response record name")
        else:
            base = self._strip_configured_suffixes(
                self._path_name(operation.method, operation.path), "response record name"
            )
        if len(self.options.include_status_codes) > 1:
            base = f"{base}{self._status_suffix(operation.status_code)}"
        return f"{base}Response"

    def _response_identity(self, operation: SelectedOperation) -> NameIdentity:
        return ("response", operation.path, operation.method, operation.status_code)

    def _status_suffix(self, status_code: str) -> str:
        if status_code.isdecimal():
            return status_code
        return self._pascal(status_code)

    def _path_name(self, method: str, path: str) -> str:
        parts = [self._pascal(method)]
        for segment in path.strip("/").split("/"):
            if not segment:
                continue
            if segment.startswith("{") and segment.endswith("}"):
                parts.append(f"By{self._pascal(segment[1:-1])}")
            else:
                parts.append(self._pascal(segment))
        return "".join(parts)

    def _field_name(self, text: str, parent_name: str) -> str:
        if self.options.field_name_case == "preserve":
            return self._require_avro_name(text, f"field {parent_name}.{text}")
        if self.options.field_name_case == "snake_case":
            name = self._snake(text)
        elif self.options.field_name_case == "camelCase":
            name = self._camel(text)
        else:
            name = self._pascal(text)
        return self._require_avro_name(name, f"field {parent_name}.{text}")

    def _enum_symbol_from_text(self, text: str) -> str:
        symbol = "_".join(self._words(text)).upper()
        return self._require_enum_symbol(symbol, f"entity type derived from {text!r}")

    def _pascal(self, text: str) -> str:
        words = self._words(text)
        if not words:
            raise AvroNameError(f"Cannot derive an Avro name from {text!r}")
        name = "".join(word[:1].upper() + word[1:] for word in words)
        if name[0].isdigit():
            name = f"N{name}"
        return name

    def _camel(self, text: str) -> str:
        pascal = self._pascal(text)
        return f"{pascal[:1].lower()}{pascal[1:]}"

    def _snake(self, text: str) -> str:
        words = self._words(text)
        if not words:
            raise AvroNameError(f"Cannot derive an Avro field name from {text!r}")
        name = "_".join(words)
        if name[0].isdigit():
            name = f"n_{name}"
        return name

    def _named_type_base(self, text: str, context: str) -> str:
        return self._strip_configured_suffixes(self._pascal(text), context, source_text=text)

    def _strip_configured_suffixes(
        self, name: str, context: str, *, source_text: str | None = None
    ) -> str:
        for suffix in self.options.remove_name_suffixes:
            self._require_avro_name(suffix, "configured name suffix")
            name_matches = name.endswith(suffix)
            source_matches = source_text is not None and source_text.endswith(suffix)
            if not name_matches and not source_matches:
                continue
            if name_matches and self._has_case_variant_suffix(source_text, suffix):
                continue
            stripped = name[: -len(suffix)]
            if not stripped:
                raise AvroNameError(
                    f"Cannot remove suffix {suffix!r} from generated Avro {context} {name!r}: "
                    "result would be empty"
                )
            return self._require_avro_name(stripped, context)
        return name

    def _has_case_variant_suffix(self, text: str | None, suffix: str) -> bool:
        if text is None:
            return False
        if len(text) < len(suffix):
            return False
        raw_suffix = text[-len(suffix) :]
        return raw_suffix.lower() == suffix.lower() and raw_suffix != suffix

    def _allocate_name(self, preferred_name: str, identity: NameIdentity) -> str:
        name = self._sanitize_avro_name(preferred_name, "generated name")
        existing_identity = self.allocated_names.get(name)
        if existing_identity is None:
            self.allocated_names[name] = identity
            return name
        if existing_identity == identity:
            return name

        suffix = 2
        while True:
            candidate = f"{name}{suffix}"
            existing_identity = self.allocated_names.get(candidate)
            if existing_identity is None:
                self.allocated_names[candidate] = identity
                return candidate
            if existing_identity == identity:
                return candidate
            suffix += 1

    def _sanitize_avro_name(self, name: str, context: str) -> str:
        words = self._words(name)
        if words:
            return self._require_avro_name(self._pascal(name), context)
        return self._require_avro_name(name, context)

    def _schema_fingerprint(self, value: Any) -> NameIdentity:
        if isinstance(value, dict):
            return (
                "dict",
                *(
                    (key, self._schema_fingerprint(item))
                    for key, item in value.items()
                    if key != "description"
                ),
            )
        if isinstance(value, list):
            return (
                "list",
                *(self._schema_fingerprint(item) for item in value),
            )
        if isinstance(value, str | int | float | bool) or value is None:
            return ("scalar", value)
        return ("repr", repr(value))

    def _words(self, text: str) -> list[str]:
        normalized = re.sub(r"[^0-9A-Za-z]+", " ", text)
        words: list[str] = []
        for chunk in normalized.split():
            words.extend(
                match.group(0).lower()
                for match in re.finditer(r"[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]?[a-z]+|[0-9]+", chunk)
            )
        return words

    def _require_avro_name(self, name: str, context: str) -> str:
        if not AVRO_NAME_RE.fullmatch(name):
            raise AvroNameError(f"Invalid Avro {context}: {name!r}")
        return name

    def _require_enum_symbol(self, symbol: str, context: str) -> str:
        if not AVRO_NAME_RE.fullmatch(symbol):
            raise AvroNameError(f"Invalid Avro enum symbol for {context}: {symbol!r}")
        return symbol

    def _validate_avro(self, schema: JsonDict) -> None:
        try:
            parse_schema(schema)
        except Exception as exc:
            raise OpenApiAvroError(f"Generated Avro schema is invalid: {exc}") from exc


def convert_openapi_to_avro(
    openapi_doc: dict[str, Any], options: GenerationOptions
) -> dict[str, Any]:
    """Convert an OpenAPI document into one Avro envelope schema.

    Args:
        openapi_doc: Parsed OpenAPI JSON/YAML document.
        options: Generation options supplied by the CLI or tests.

    Returns:
        A JSON-serializable Avro schema dictionary.

    Raises:
        OpenApiAvroError: If the document cannot be converted under the selected policies.
    """
    return _Converter(openapi_doc, options).convert()


class _ReferencedSchemaRenderer:
    def __init__(
        self,
        bundled_schema: JsonDict,
        *,
        namespace: str,
        root_name: str,
        subject_template: str,
        root_subject: str | None = None,
    ) -> None:
        self.bundled_schema = bundled_schema
        self.namespace = namespace
        self.root_name = root_name
        self.subject_template = subject_template
        self.root_subject = root_subject
        self.definitions: OrderedDict[str, JsonDict] = OrderedDict()
        self.name_to_fullname: dict[str, str] = {}

    def render(self) -> ReferencedSchemaSet:
        self._collect_named_definitions(self.bundled_schema, default_namespace=self.namespace)
        dependencies: dict[str, tuple[str, ...]] = {}
        schemas: dict[str, JsonDict] = {}
        for fullname, schema in self.definitions.items():
            collected_dependencies: list[str] = []
            schemas[fullname] = self._standalone_schema(schema, fullname, collected_dependencies)
            dependencies[fullname] = tuple(dict.fromkeys(collected_dependencies))

        ordered_fullnames = self._registration_order(dependencies)
        root_fullname = f"{self.namespace}.{self.root_name}"
        artifacts = tuple(
            ReferencedSchemaArtifact(
                fullname=fullname,
                subject=self._subject(fullname, root_fullname=root_fullname),
                filename=f"{fullname}.avsc",
                schema=schemas[fullname],
                references=tuple(
                    SchemaRegistryReference(
                        name=dependency,
                        subject=self._subject(dependency, root_fullname=root_fullname),
                    )
                    for dependency in dependencies[fullname]
                ),
            )
            for fullname in ordered_fullnames
        )
        return ReferencedSchemaSet(bundled_schema=self.bundled_schema, artifacts=artifacts)

    def _collect_named_definitions(self, value: Any, *, default_namespace: str) -> None:
        if isinstance(value, dict):
            schema_type = value.get("type")
            nested_namespace = default_namespace
            if (
                isinstance(schema_type, str)
                and schema_type in {"record", "enum", "fixed"}
                and isinstance(value.get("name"), str)
            ):
                fullname = self._fullname(value, default_namespace)
                self.definitions.setdefault(fullname, value)
                simple_name = fullname.rsplit(".", 1)[-1]
                self.name_to_fullname[simple_name] = fullname
                self.name_to_fullname[fullname] = fullname
                nested_namespace = fullname.rsplit(".", 1)[0]
            for child in value.values():
                self._collect_named_definitions(child, default_namespace=nested_namespace)
        elif isinstance(value, list):
            for child in value:
                self._collect_named_definitions(child, default_namespace=default_namespace)

    def _standalone_schema(
        self, schema: JsonDict, owner_fullname: str, dependencies: list[str]
    ) -> JsonDict:
        rendered: JsonDict = {}
        for key, value in schema.items():
            if key == "namespace":
                continue
            if key == "name":
                rendered[key] = owner_fullname.rsplit(".", 1)[-1]
                continue
            rendered[key] = self._render_type(value, owner_fullname, dependencies)
        rendered["namespace"] = owner_fullname.rsplit(".", 1)[0]
        return self._order_named_schema(rendered)

    def _render_type(self, value: Any, owner_fullname: str, dependencies: list[str]) -> Any:
        if isinstance(value, dict):
            return self._render_dict_type(value, owner_fullname, dependencies)
        if isinstance(value, list):
            return [self._render_type(child, owner_fullname, dependencies) for child in value]
        if isinstance(value, str) and value not in PRIMITIVE_AVRO_TYPES:
            return self._render_string_reference(value, owner_fullname, dependencies)
        return value

    def _render_dict_type(
        self, value: JsonDict, owner_fullname: str, dependencies: list[str]
    ) -> Any:
        schema_type = value.get("type")
        if (
            isinstance(schema_type, str)
            and schema_type in {"record", "enum", "fixed"}
            and isinstance(value.get("name"), str)
        ):
            fullname = self._fullname(value, owner_fullname.rsplit(".", 1)[0])
            if fullname != owner_fullname:
                dependencies.append(fullname)
            return fullname
        return {
            key: self._render_type(child, owner_fullname, dependencies)
            for key, child in value.items()
        }

    def _render_string_reference(
        self, value: str, owner_fullname: str, dependencies: list[str]
    ) -> str:
        fullname = self.name_to_fullname.get(value)
        if fullname is None:
            return value
        if fullname != owner_fullname:
            dependencies.append(fullname)
        return fullname

    def _order_named_schema(self, schema: JsonDict) -> JsonDict:
        ordered: JsonDict = {}
        for key in ("type", "namespace", "name", "doc", "symbols", "fields", "size"):
            if key in schema:
                ordered[key] = schema[key]
        for key, value in schema.items():
            if key not in ordered:
                ordered[key] = value
        return ordered

    def _registration_order(self, dependencies: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
        ordered: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(fullname: str) -> None:
            if fullname in visited:
                return
            if fullname in visiting:
                return
            visiting.add(fullname)
            for dependency in dependencies[fullname]:
                if dependency in dependencies:
                    visit(dependency)
            visiting.remove(fullname)
            visited.add(fullname)
            ordered.append(fullname)

        for fullname in self.definitions:
            visit(fullname)
        return tuple(ordered)

    def _fullname(self, schema: JsonDict, default_namespace: str) -> str:
        name = schema.get("name")
        if not isinstance(name, str):
            raise OpenApiAvroError("Named Avro schema is missing a string name")
        if "." in name:
            return name
        namespace = schema.get("namespace")
        if isinstance(namespace, str) and namespace:
            return f"{namespace}.{name}"
        return f"{default_namespace}.{name}"

    def _subject(self, fullname: str, *, root_fullname: str) -> str:
        if fullname == root_fullname and self.root_subject is not None:
            return self.root_subject
        namespace, name = fullname.rsplit(".", 1)
        try:
            return self.subject_template.format(
                fullname=fullname,
                namespace=namespace,
                name=name,
                rootname=self.root_name,
            )
        except KeyError as exc:
            raise OpenApiAvroError(
                f"Unknown placeholder {{{exc.args[0]}}} in reference subject template"
            ) from exc


def convert_openapi_to_referenced_avro(
    openapi_doc: dict[str, Any],
    options: GenerationOptions,
    *,
    subject_template: str = "{fullname}",
    root_subject: str | None = None,
) -> ReferencedSchemaSet:
    """Convert OpenAPI to bundled Avro plus Confluent-friendly schema references."""
    bundled_schema = _Converter(openapi_doc, options).convert()
    return _ReferencedSchemaRenderer(
        bundled_schema,
        namespace=options.namespace,
        root_name=options.root_name,
        subject_template=subject_template,
        root_subject=root_subject,
    ).render()
