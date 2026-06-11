from __future__ import annotations

from pathlib import Path

import pytest
from fastavro import parse_schema
from ruamel.yaml import YAML

from openapi_get_avro.converter import convert_openapi_to_avro
from openapi_get_avro.exceptions import UnsupportedSchemaError
from openapi_get_avro.models import GenerationOptions

EXAMPLES = Path(__file__).parents[1] / "examples"


def load_yaml(name: str) -> dict[str, object]:
    loaded = YAML(typ="safe").load((EXAMPLES / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _base_doc(paths: dict[str, object], schemas: dict[str, object]) -> dict[str, object]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Composition API"},
        "paths": paths,
        "components": {"schemas": schemas},
    }


def _json_response(schema: dict[str, object]) -> dict[str, object]:
    return {
        "200": {
            "description": "OK",
            "content": {"application/json": {"schema": schema}},
        }
    }


def _options(**overrides: object) -> GenerationOptions:
    values = {
        "namespace": "com.example.composition",
        "root_name": "CompositionEnvelope",
        **overrides,
    }
    return GenerationOptions(**values)


def _data_branches(schema: dict[str, object]) -> list[object]:
    fields = schema["fields"]
    assert isinstance(fields, list)
    data_field = fields[-1]
    assert isinstance(data_field, dict)
    branches = data_field["type"]
    assert isinstance(branches, list)
    return branches


def _record_fields(record: dict[str, object]) -> dict[str, dict[str, object]]:
    fields = record["fields"]
    assert isinstance(fields, list)
    typed_fields: dict[str, dict[str, object]] = {}
    for field in fields:
        assert isinstance(field, dict)
        name = field["name"]
        assert isinstance(name, str)
        typed_fields[name] = field
    return typed_fields


def test_complex_fixture_flattens_all_of_and_maps_one_of_to_union() -> None:
    openapi_doc = load_yaml("complex.openapi.yaml")

    schema = convert_openapi_to_avro(
        openapi_doc,
        GenerationOptions(namespace="com.example.sports", root_name="SportsEnvelope"),
    )

    assert schema["doc"] == "Complex fixture for composition, arrays, maps, and oneOf."
    branches = _data_branches(schema)
    assert [branch["name"] for branch in branches if isinstance(branch, dict)] == [
        "SearchEntitiesResponse",
        "GetTeamResponse",
    ]

    search_response = branches[0]
    assert isinstance(search_response, dict)
    search_fields = _record_fields(search_response)
    items = search_fields["items"]["type"]
    assert isinstance(items, dict)
    item_union = items["items"]
    assert isinstance(item_union, list)
    assert [branch["name"] for branch in item_union if isinstance(branch, dict)] == [
        "Team",
        "Venue",
    ]

    team = item_union[0]
    assert isinstance(team, dict)
    team_fields = _record_fields(team)
    assert list(team_fields) == ["id", "name", "aliases", "metadata"]
    assert team_fields["id"]["type"] == {"type": "string", "logicalType": "uuid"}
    assert team_fields["name"]["type"] == "string"
    assert team_fields["aliases"]["type"] == [
        "null",
        {"type": "array", "items": "string"},
    ]
    assert team_fields["metadata"]["type"] == [
        "null",
        {"type": "map", "values": "string"},
    ]

    venue = item_union[1]
    assert isinstance(venue, dict)
    venue_fields = _record_fields(venue)
    assert venue_fields["opened"]["type"] == [
        "null",
        {"type": "int", "logicalType": "date"},
    ]

    get_team_response = branches[1]
    assert isinstance(get_team_response, dict)
    assert list(_record_fields(get_team_response)) == ["id", "name", "aliases", "metadata"]
    parse_schema(schema)


def test_all_of_conflicting_fields_fail_in_strict_mode() -> None:
    openapi_doc = _base_doc(
        {
            "/conflict": {
                "get": {
                    "operationId": "getConflict",
                    "tags": ["Conflict"],
                    "responses": _json_response({"$ref": "#/components/schemas/Conflict"}),
                }
            }
        },
        {
            "Conflict": {
                "allOf": [
                    {"type": "object", "properties": {"id": {"type": "string"}}},
                    {"type": "object", "properties": {"id": {"type": "integer"}}},
                ]
            }
        },
    )

    with pytest.raises(UnsupportedSchemaError, match="Conflicting allOf field 'id'"):
        convert_openapi_to_avro(openapi_doc, _options())


def test_any_of_fails_by_default() -> None:
    openapi_doc = _base_doc(
        {
            "/search": {
                "get": {
                    "operationId": "search",
                    "tags": ["Search"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "required": ["item"],
                            "properties": {
                                "item": {
                                    "anyOf": [
                                        {"$ref": "#/components/schemas/Team"},
                                        {"$ref": "#/components/schemas/Venue"},
                                    ]
                                }
                            },
                        }
                    ),
                }
            }
        },
        {
            "Team": {"type": "object", "properties": {"name": {"type": "string"}}},
            "Venue": {"type": "object", "properties": {"name": {"type": "string"}}},
        },
    )

    with pytest.raises(UnsupportedSchemaError, match="anyOf"):
        convert_openapi_to_avro(openapi_doc, _options())


def test_any_of_can_map_to_union_when_policy_allows_it() -> None:
    openapi_doc = _base_doc(
        {
            "/search": {
                "get": {
                    "operationId": "search",
                    "tags": ["Search"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "required": ["item"],
                            "properties": {
                                "item": {
                                    "anyOf": [
                                        {"$ref": "#/components/schemas/Team"},
                                        {"$ref": "#/components/schemas/Venue"},
                                    ]
                                }
                            },
                        }
                    ),
                }
            }
        },
        {
            "Team": {"type": "object", "properties": {"name": {"type": "string"}}},
            "Venue": {"type": "object", "properties": {"name": {"type": "string"}}},
        },
    )

    schema = convert_openapi_to_avro(openapi_doc, _options(any_of_policy="union"))

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    fields = _record_fields(branch)
    item_type = fields["item"]["type"]
    assert isinstance(item_type, list)
    assert [branch["name"] for branch in item_type if isinstance(branch, dict)] == [
        "Team",
        "Venue",
    ]
    parse_schema(schema)
