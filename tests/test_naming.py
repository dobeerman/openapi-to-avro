from __future__ import annotations

import pytest

from openapi_get_avro.converter import convert_openapi_to_avro
from openapi_get_avro.exceptions import AvroNameError, UnsupportedSchemaError
from openapi_get_avro.models import GenerationOptions


def _base_doc(
    paths: dict[str, object], schemas: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Naming API"},
        "paths": paths,
        "components": {"schemas": schemas or {}},
    }


def _json_response(schema: dict[str, object]) -> dict[str, object]:
    return {
        "200": {
            "description": "OK",
            "content": {"application/json": {"schema": schema}},
        }
    }


def _options() -> GenerationOptions:
    return GenerationOptions(namespace="com.example.naming", root_name="NamingEnvelope")


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


def test_path_fallback_names_path_parameters_with_by_prefix() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/matches/{matchId}/lineups": {
                    "get": {
                        "tags": ["Match"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "properties": {"id": {"type": "string"}},
                            }
                        ),
                    }
                }
            }
        ),
        _options(),
    )

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    assert branch["name"] == "GetMatchesByMatchIdLineupsResponse"


def test_duplicate_operation_ids_receive_deterministic_numeric_suffixes() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/alpha": {
                    "get": {
                        "operationId": "getThing",
                        "tags": ["Alpha"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "properties": {"alpha": {"type": "string"}},
                            }
                        ),
                    }
                },
                "/beta": {
                    "get": {
                        "operationId": "getThing",
                        "tags": ["Beta"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "properties": {"beta": {"type": "string"}},
                            }
                        ),
                    }
                },
            }
        ),
        _options(),
    )

    branches = _data_branches(schema)
    assert [branch["name"] for branch in branches if isinstance(branch, dict)] == [
        "GetThingResponse",
        "GetThingResponse2",
    ]


def test_remove_name_suffixes_keeps_current_output_unchanged_by_default() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/attributes": {
                    "get": {
                        "operationId": "getAttributeDto",
                        "tags": ["Attribute"],
                        "responses": _json_response({"$ref": "#/components/schemas/AttributeDto"}),
                    }
                }
            },
            {
                "AttributeDto": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                }
            },
        ),
        _options(),
    )

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    assert branch["name"] == "GetAttributeDtoResponse"
    assert branch["fields"] == [
        {
            "name": "id",
            "type": ["null", "string"],
            "default": None,
        }
    ]


def test_remove_name_suffixes_renames_component_refs_and_response_records() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/attributes": {
                    "get": {
                        "operationId": "getAttributeDto",
                        "tags": ["Attribute"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "required": ["attributeDto", "roleDto"],
                                "properties": {
                                    "attributeDto": {"$ref": "#/components/schemas/AttributeDto"},
                                    "roleDto": {
                                        "type": "object",
                                        "required": ["id"],
                                        "properties": {"id": {"type": "string"}},
                                    },
                                },
                            }
                        ),
                    }
                }
            },
            {
                "AttributeDto": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                }
            },
        ),
        GenerationOptions(
            namespace="com.example.naming",
            root_name="NamingEnvelope",
            remove_name_suffixes=("Dto",),
        ),
    )

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    assert branch["name"] == "GetAttributeResponse"
    fields = _record_fields(branch)
    assert list(fields) == ["attributeDto", "roleDto"]
    assert isinstance(fields["attributeDto"]["type"], dict)
    assert fields["attributeDto"]["type"]["name"] == "Attribute"
    assert isinstance(fields["roleDto"]["type"], dict)
    assert fields["roleDto"]["type"]["name"] == "GetAttributeResponseRole"


def test_field_name_case_snake_case_transforms_payload_fields_only() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/lineups": {
                    "get": {
                        "operationId": "getLineupDto",
                        "tags": ["Lineup"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "required": ["lineupVersion", "status"],
                                "properties": {
                                    "lineupVersion": {"type": "integer"},
                                    "status": {
                                        "type": "string",
                                        "enum": ["Draft", "Published"],
                                    },
                                    "teamMember": {
                                        "type": "object",
                                        "required": ["displayName"],
                                        "properties": {
                                            "displayName": {"type": "string"},
                                        },
                                    },
                                },
                            }
                        ),
                    }
                }
            }
        ),
        GenerationOptions(
            namespace="com.example.naming",
            root_name="NamingEnvelope",
            field_name_case="snake_case",
        ),
    )

    root_fields = schema["fields"]
    assert isinstance(root_fields, list)
    assert [field["name"] for field in root_fields if isinstance(field, dict)] == [
        "id",
        "timestamp",
        "operation",
        "entity_type",
        "data",
    ]

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    assert branch["name"] == "GetLineupDtoResponse"
    fields = _record_fields(branch)
    assert list(fields) == ["lineup_version", "status", "team_member"]
    assert fields["status"]["type"] == {
        "type": "enum",
        "name": "GetLineupDtoResponseStatusEnum",
        "symbols": ["Draft", "Published"],
    }
    team_member = fields["team_member"]["type"]
    assert isinstance(team_member, list)
    team_member_record = team_member[1]
    assert isinstance(team_member_record, dict)
    assert team_member_record["name"] == "GetLineupDtoResponseTeamMember"
    assert list(_record_fields(team_member_record)) == ["display_name"]


def test_field_name_case_supports_camel_and_pascal_case() -> None:
    openapi_doc = _base_doc(
        {
            "/lineups": {
                "get": {
                    "operationId": "getLineup",
                    "tags": ["Lineup"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {
                                "lineup_version": {"type": "integer"},
                                "home-team-id": {"type": "string"},
                            },
                        }
                    ),
                }
            }
        }
    )

    camel = convert_openapi_to_avro(
        openapi_doc,
        GenerationOptions(
            namespace="com.example.naming",
            root_name="NamingEnvelope",
            field_name_case="camelCase",
        ),
    )
    pascal = convert_openapi_to_avro(
        openapi_doc,
        GenerationOptions(
            namespace="com.example.naming",
            root_name="NamingEnvelope",
            field_name_case="PascalCase",
        ),
    )

    camel_branch = _data_branches(camel)[0]
    pascal_branch = _data_branches(pascal)[0]
    assert isinstance(camel_branch, dict)
    assert isinstance(pascal_branch, dict)
    assert list(_record_fields(camel_branch)) == ["lineupVersion", "homeTeamId"]
    assert list(_record_fields(pascal_branch)) == ["LineupVersion", "HomeTeamId"]


def test_field_name_case_fails_when_transform_creates_duplicate_field_names() -> None:
    with pytest.raises(AvroNameError, match="duplicate Avro field"):
        convert_openapi_to_avro(
            _base_doc(
                {
                    "/lineups": {
                        "get": {
                            "operationId": "getLineup",
                            "tags": ["Lineup"],
                            "responses": _json_response(
                                {
                                    "type": "object",
                                    "properties": {
                                        "lineupVersion": {"type": "integer"},
                                        "lineup_version": {"type": "integer"},
                                    },
                                }
                            ),
                        }
                    }
                }
            ),
            GenerationOptions(
                namespace="com.example.naming",
                root_name="NamingEnvelope",
                field_name_case="snake_case",
            ),
        )


def test_remove_name_suffixes_resolves_collisions_deterministically() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/attributes": {
                    "get": {
                        "operationId": "getAttributes",
                        "tags": ["Attribute"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "required": ["dto", "plain"],
                                "properties": {
                                    "dto": {"$ref": "#/components/schemas/AttributeDto"},
                                    "plain": {"$ref": "#/components/schemas/Attribute"},
                                },
                            }
                        ),
                    }
                }
            },
            {
                "AttributeDto": {
                    "type": "object",
                    "properties": {"dtoId": {"type": "string"}},
                },
                "Attribute": {
                    "type": "object",
                    "properties": {"plainId": {"type": "string"}},
                },
            },
        ),
        GenerationOptions(
            namespace="com.example.naming",
            root_name="NamingEnvelope",
            remove_name_suffixes=("Dto",),
        ),
    )

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    fields = _record_fields(branch)
    assert isinstance(fields["dto"]["type"], dict)
    assert isinstance(fields["plain"]["type"], dict)
    assert fields["dto"]["type"]["name"] == "Attribute"
    assert fields["plain"]["type"]["name"] == "Attribute2"


def test_remove_name_suffixes_is_case_sensitive() -> None:
    openapi_doc = _base_doc(
        {
            "/attributes": {
                "get": {
                    "operationId": "getAttributes",
                    "tags": ["Attribute"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "required": ["attribute"],
                            "properties": {
                                "attribute": {"$ref": "#/components/schemas/AttributeDTO"}
                            },
                        }
                    ),
                }
            }
        },
        {
            "AttributeDTO": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
            }
        },
    )

    unchanged = convert_openapi_to_avro(
        openapi_doc,
        GenerationOptions(
            namespace="com.example.naming",
            root_name="NamingEnvelope",
            remove_name_suffixes=("Dto",),
        ),
    )
    stripped = convert_openapi_to_avro(
        openapi_doc,
        GenerationOptions(
            namespace="com.example.naming",
            root_name="NamingEnvelope",
            remove_name_suffixes=("DTO",),
        ),
    )

    unchanged_branch = _data_branches(unchanged)[0]
    stripped_branch = _data_branches(stripped)[0]
    assert isinstance(unchanged_branch, dict)
    assert isinstance(stripped_branch, dict)
    unchanged_fields = _record_fields(unchanged_branch)
    stripped_fields = _record_fields(stripped_branch)
    assert isinstance(unchanged_fields["attribute"]["type"], dict)
    assert isinstance(stripped_fields["attribute"]["type"], dict)
    assert unchanged_fields["attribute"]["type"]["name"] == "AttributeDto"
    assert stripped_fields["attribute"]["type"]["name"] == "Attribute"


def test_component_refs_are_inlined_once_then_reused_by_name() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/fixture": {
                    "get": {
                        "operationId": "getFixture",
                        "tags": ["Fixture"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "required": ["home", "away"],
                                "properties": {
                                    "home": {"$ref": "#/components/schemas/Team"},
                                    "away": {"$ref": "#/components/schemas/Team"},
                                },
                            }
                        ),
                    }
                }
            },
            {
                "Team": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "string"}},
                }
            },
        ),
        _options(),
    )

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    fields = branch["fields"]
    assert isinstance(fields, list)
    home_field = fields[0]
    away_field = fields[1]
    assert isinstance(home_field, dict)
    assert isinstance(away_field, dict)
    assert isinstance(home_field["type"], dict)
    assert home_field["type"]["name"] == "Team"
    assert away_field["type"] == "Team"


def test_component_enum_refs_are_defined_with_component_name_then_reused() -> None:
    schema = convert_openapi_to_avro(
        _base_doc(
            {
                "/members": {
                    "get": {
                        "operationId": "listMembers",
                        "tags": ["Member"],
                        "responses": _json_response(
                            {
                                "type": "object",
                                "required": ["primary", "secondary"],
                                "properties": {
                                    "primary": {"$ref": "#/components/schemas/MemberType"},
                                    "secondary": {"$ref": "#/components/schemas/MemberType"},
                                },
                            }
                        ),
                    }
                }
            },
            {
                "MemberType": {
                    "type": "string",
                    "enum": ["unknown", "team", "federation"],
                }
            },
        ),
        _options(),
    )

    branch = _data_branches(schema)[0]
    assert isinstance(branch, dict)
    fields = branch["fields"]
    assert isinstance(fields, list)
    primary = fields[0]
    secondary = fields[1]
    assert isinstance(primary, dict)
    assert isinstance(secondary, dict)
    assert primary["type"] == {
        "type": "enum",
        "name": "MemberType",
        "symbols": ["unknown", "team", "federation"],
    }
    assert secondary["type"] == "MemberType"


def test_external_ref_fails_with_clear_project_error() -> None:
    with pytest.raises(UnsupportedSchemaError, match="Unsupported \\$ref"):
        convert_openapi_to_avro(
            _base_doc(
                {
                    "/external": {
                        "get": {
                            "operationId": "getExternal",
                            "tags": ["External"],
                            "responses": _json_response(
                                {
                                    "$ref": "https://example.com/openapi.yaml#/components/schemas/Thing"
                                }
                            ),
                        }
                    }
                }
            ),
            _options(),
        )


def test_invalid_enum_symbols_fail_in_strict_mode() -> None:
    with pytest.raises(AvroNameError, match="Invalid Avro enum symbol"):
        convert_openapi_to_avro(
            _base_doc(
                {
                    "/status": {
                        "get": {
                            "operationId": "getStatus",
                            "tags": ["Status"],
                            "responses": _json_response(
                                {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "enum": ["IN_PLAY", "not valid"],
                                        }
                                    },
                                }
                            ),
                        }
                    }
                }
            ),
            _options(),
        )
