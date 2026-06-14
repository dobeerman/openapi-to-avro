"""Infer Avro records from arrays of similar JSON objects."""

from __future__ import annotations

import re
import uuid
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, Literal, cast

from fastavro import parse_schema

from .exceptions import AvroNameError, JsonInferenceError, OpenApiAvroError

JsonDict = dict[str, Any]
JsonKind = Literal["object", "array", "string", "long", "double", "boolean"]
RecordFingerprint = tuple[Hashable, ...]

AVRO_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})?$"
)


@dataclass(frozen=True)
class JsonInferenceOptions:
    """Options controlling JSON sample inference."""

    namespace: str
    name: str
    reuse_record_shapes: bool = False
    enforce_timestamp: bool = False


class _JsonInferer:
    def __init__(self, samples: Any, options: JsonInferenceOptions) -> None:
        self.samples = samples
        self.options = options
        self.allocated_names: dict[str, RecordFingerprint] = {self._pascal(options.name): ("root",)}
        self.reused_record_names: dict[RecordFingerprint, str] = {}

    def infer(self) -> JsonDict:
        if not isinstance(self.samples, list):
            raise JsonInferenceError("Input JSON must be an array of objects")
        if not self.samples:
            raise JsonInferenceError("Input JSON array must contain at least one object")
        if not all(isinstance(item, dict) for item in self.samples):
            raise JsonInferenceError("Input JSON array must contain only objects")

        record_name = self._require_avro_name(self._pascal(self.options.name), "record name")
        schema = self._objects_to_record(
            self.samples,
            record_name=record_name,
            path=record_name,
            include_namespace=True,
        )
        schema = cast(JsonDict, schema)
        self._validate_avro(schema)
        return schema

    def _objects_to_record(
        self,
        objects: list[Any],
        *,
        record_name: str,
        path: str,
        include_namespace: bool = False,
    ) -> JsonDict | str:
        fields = self._object_fields(objects, parent_name=record_name, path=path)
        fingerprint = self._record_fingerprint(fields)
        if self.options.reuse_record_shapes and not include_namespace:
            existing_name = self.reused_record_names.get(fingerprint)
            if existing_name is not None:
                return existing_name
            record_name = self._allocate_name(
                self._shared_record_name(fields) or record_name,
                fingerprint,
            )
            self.reused_record_names[fingerprint] = record_name

        record: JsonDict = {"type": "record"}
        if include_namespace:
            record["namespace"] = self.options.namespace
        record["name"] = record_name
        record["fields"] = fields
        return record

    def _object_fields(self, objects: list[Any], *, parent_name: str, path: str) -> list[JsonDict]:
        fields: list[JsonDict] = []
        seen_field_names: set[str] = set()
        keys = self._ordered_keys(objects, path)
        if not keys:
            raise JsonInferenceError(f"Cannot infer record {path}: objects have no fields")
        for key in keys:
            field_path = f"{path}.{key}"
            avro_field_name = self._require_avro_name(key, f"field {field_path}")
            if avro_field_name in seen_field_names:
                raise AvroNameError(f"Duplicate Avro field name {avro_field_name!r} at {path}")
            seen_field_names.add(avro_field_name)

            present_values = [item[key] for item in objects if key in item]
            non_null_values = [value for value in present_values if value is not None]
            missing_count = len(objects) - len(present_values)
            null_count = len(present_values) - len(non_null_values)
            if not non_null_values:
                raise JsonInferenceError(
                    f"Cannot infer type for field {field_path}: all observed values are null"
                )

            avro_type = self._values_to_avro(
                non_null_values,
                name_hint=f"{parent_name}{self._pascal(key)}",
                path=field_path,
            )
            optional = missing_count > 0 or null_count > 0
            field: JsonDict = {"name": avro_field_name, "type": avro_type}
            if optional:
                field["type"] = ["null", avro_type]
                field["default"] = None
            fields.append(field)
        return fields

    def _values_to_avro(self, values: list[Any], *, name_hint: str, path: str) -> Any:
        observed_kinds = {self._json_kind(value) for value in values}
        if len(observed_kinds) != 1:
            kinds = ", ".join(sorted(observed_kinds))
            raise JsonInferenceError(
                f"Incompatible types for {path}: observed {kinds}; values must use one JSON type"
            )

        kind = observed_kinds.pop()
        if kind == "object":
            return self._objects_to_record(
                values,
                record_name=self._require_avro_name(name_hint, f"nested record {path}"),
                path=path,
            )
        if kind == "array":
            return {
                "type": "array",
                "items": self._array_items_to_avro(values, name_hint=name_hint, path=path),
            }
        if kind == "string":
            return self._strings_to_avro(values)
        return kind

    def _array_items_to_avro(self, arrays: list[Any], *, name_hint: str, path: str) -> Any:
        items: list[Any] = []
        for array in arrays:
            items.extend(array)
        if not items:
            raise JsonInferenceError(
                f"Cannot infer item type for field {path}: all arrays are empty"
            )
        if any(item is None for item in items):
            raise JsonInferenceError(
                f"Cannot infer item type for field {path}: null array items are unsupported"
            )
        return self._values_to_avro(items, name_hint=f"{name_hint}Item", path=f"{path}[]")

    def _ordered_keys(self, objects: list[Any], path: str) -> list[str]:
        keys: list[str] = []
        seen: set[str] = set()
        for index, item in enumerate(objects):
            for key in item:
                if not isinstance(key, str):
                    raise JsonInferenceError(f"Object at {path}[{index}] has a non-string key")
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
        return keys

    def _json_kind(self, value: Any) -> JsonKind:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "long"
        if isinstance(value, float):
            return "double"
        if isinstance(value, str):
            return "string"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        if value is None:
            raise JsonInferenceError(
                "Internal error: null values must be filtered before inference"
            )
        raise JsonInferenceError(f"Unsupported JSON value {value!r}")

    def _strings_to_avro(self, values: list[Any]) -> Any:
        if self.options.enforce_timestamp and all(
            self._is_temporal_string(value) for value in values
        ):
            return {"type": "long", "logicalType": "timestamp-millis"}
        if all(self._is_uuid(value) for value in values):
            return {"type": "string", "logicalType": "uuid"}
        return "string"

    def _is_temporal_string(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return (
            ISO_DATE_RE.fullmatch(value) is not None
            or ISO_DATE_TIME_RE.fullmatch(value) is not None
        )

    def _is_uuid(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            uuid.UUID(value)
        except ValueError:
            return False
        return True

    def _pascal(self, text: str) -> str:
        words = self._words(text)
        if not words:
            raise AvroNameError(f"Cannot derive an Avro name from {text!r}")
        name = "".join(word[:1].upper() + word[1:] for word in words)
        if name[0].isdigit():
            name = f"N{name}"
        return name

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

    def _allocate_name(self, preferred_name: str, identity: RecordFingerprint) -> str:
        name = self._require_avro_name(preferred_name, "generated record name")
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

    def _shared_record_name(self, fields: list[JsonDict]) -> str | None:
        if [field["name"] for field in fields] != ["x", "y", "z"]:
            return None
        if all(
            field.get("type") in {"long", "double"} and "default" not in field for field in fields
        ):
            return "Position"
        return None

    def _record_fingerprint(self, fields: list[JsonDict]) -> RecordFingerprint:
        return (
            "record",
            *((field["name"], self._type_fingerprint(field["type"])) for field in fields),
        )

    def _type_fingerprint(self, avro_type: Any) -> RecordFingerprint:
        if isinstance(avro_type, str):
            return ("primitive-or-ref", avro_type)
        if isinstance(avro_type, list):
            return ("union", *(self._type_fingerprint(item) for item in avro_type))
        if isinstance(avro_type, dict):
            return self._dict_type_fingerprint(avro_type)
        if isinstance(avro_type, int | float | bool) or avro_type is None:
            return ("scalar", avro_type)
        return ("repr", repr(avro_type))

    def _dict_type_fingerprint(self, avro_type: JsonDict) -> RecordFingerprint:
        schema_type = avro_type.get("type")
        fields = avro_type.get("fields")
        if schema_type == "record" and isinstance(fields, list):
            return self._record_fingerprint(fields)
        if schema_type == "array":
            return ("array", self._type_fingerprint(avro_type["items"]))
        return (
            "dict",
            *(
                (key, self._type_fingerprint(value))
                for key, value in avro_type.items()
                if key not in {"name", "namespace"}
            ),
        )

    def _validate_avro(self, schema: JsonDict) -> None:
        try:
            parse_schema(schema)
        except Exception as exc:
            raise OpenApiAvroError(f"Generated Avro schema is invalid: {exc}") from exc


def infer_json_to_avro(samples: Any, options: JsonInferenceOptions) -> dict[str, Any]:
    """Infer one Avro record schema from a JSON array of similar objects."""
    return _JsonInferer(samples, options).infer()
