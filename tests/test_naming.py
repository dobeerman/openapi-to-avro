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
