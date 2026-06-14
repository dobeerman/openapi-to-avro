"""Typed configuration models for schema generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NameStrategy = Literal["operationId", "path"]
FieldNameCase = Literal["preserve", "snake_case", "camelCase", "PascalCase"]
UnknownObjectPolicy = Literal["map", "string", "empty-record", "fail"]
AnyOfPolicy = Literal["fail", "union"]
EnumPolicy = Literal["fail", "string", "sanitize"]


@dataclass(frozen=True)
class GenerationOptions:
    """Options controlling OpenAPI to Avro generation."""

    namespace: str
    root_name: str
    include_status_codes: tuple[str, ...] = ("200",)
    content_type: str = "application/json"
    strict: bool = True
    name_strategy: NameStrategy = "operationId"
    field_name_case: FieldNameCase = "preserve"
    unknown_object_policy: UnknownObjectPolicy = "fail"
    any_of_policy: AnyOfPolicy = "fail"
    enum_policy: EnumPolicy = "fail"
    timestamp_logical_type: Literal["timestamp-millis", "string"] = "timestamp-millis"
    enforce_timestamp: bool = False
    remove_name_suffixes: tuple[str, ...] = ()
    include_response_records: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchemaRegistryReference:
    """Confluent Schema Registry reference metadata for one dependency."""

    name: str
    subject: str
    version: str = "latest"


@dataclass(frozen=True)
class ReferencedSchemaArtifact:
    """A standalone Avro schema and its registry metadata."""

    fullname: str
    subject: str
    filename: str
    schema: dict[str, object]
    references: tuple[SchemaRegistryReference, ...] = ()


@dataclass(frozen=True)
class ReferencedSchemaSet:
    """Bundled schema plus deterministic referenced-schema artifacts."""

    bundled_schema: dict[str, object]
    artifacts: tuple[ReferencedSchemaArtifact, ...]


@dataclass(frozen=True)
class SelectedOperation:
    """A GET operation selected for Avro generation."""

    path: str
    method: str
    operation_id: str | None
    status_code: str
    response_description: str | None
    schema: dict[str, object]
