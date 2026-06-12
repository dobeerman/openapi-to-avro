from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastavro import parse_schema
from typer.testing import CliRunner

from openapi_get_avro.cli import app
from openapi_get_avro.converter import convert_openapi_to_avro
from openapi_get_avro.exceptions import InvalidOpenApiError
from openapi_get_avro.models import GenerationOptions


def _json_response(schema: dict[str, object]) -> dict[str, object]:
    return {
        "200": {
            "description": "OK",
            "content": {"application/json": {"schema": schema}},
        }
    }


def _doc() -> dict[str, object]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Filtered API"},
        "paths": {
            "/api/match-participants": {
                "get": {
                    "operationId": "getApiMatchParticipants",
                    "tags": ["MatchParticipant"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "person": {"$ref": "#/components/schemas/Person"},
                            },
                        }
                    ),
                }
            },
            "/api/match-participants/{id}": {
                "get": {
                    "operationId": "getApiMatchParticipantsById",
                    "tags": ["MatchParticipant"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                        }
                    ),
                }
            },
            "/api/match-participants/matchofficials": {
                "get": {
                    "operationId": "getApiMatchParticipantsMatchofficials",
                    "tags": ["MatchParticipant"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                        }
                    ),
                }
            },
            "/api/teams": {
                "get": {
                    "operationId": "getApiTeams",
                    "tags": ["Team"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                        }
                    ),
                }
            },
            "/api/venues": {
                "get": {
                    "operationId": "getApiVenues",
                    "tags": ["Venue"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "address": {"$ref": "#/components/schemas/Address"},
                            },
                        }
                    ),
                }
            },
            "/api/venues/{id}": {
                "get": {
                    "operationId": "getApiVenuesById",
                    "tags": ["Venue"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                        }
                    ),
                }
            },
            "/api/venues/attributes": {
                "get": {
                    "operationId": "getApiVenuesAttributes",
                    "tags": ["Venue"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                        }
                    ),
                }
            },
            "/api/venues/slim": {
                "get": {
                    "operationId": "getApiVenuesSlim",
                    "tags": ["Venue"],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                        }
                    ),
                }
            },
        },
        "components": {
            "schemas": {
                "Address": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
                "Person": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            }
        },
    }


def _data_branch_names(schema: dict[str, object]) -> list[str]:
    data_field = schema["fields"][-1]
    assert isinstance(data_field, dict)
    branches = data_field["type"]
    assert isinstance(branches, list)
    return [branch["name"] for branch in branches if isinstance(branch, dict)]


def test_include_response_records_filters_bundled_data_and_references() -> None:
    schema = convert_openapi_to_avro(
        _doc(),
        GenerationOptions(
            namespace="com.example.filtered",
            root_name="FilteredEnvelope",
            include_status_codes=("200", "default"),
            include_response_records=("Venues", "MatchParticipants"),
        ),
    )

    assert _data_branch_names(schema) == [
        "GetApiMatchParticipants200Response",
        "GetApiVenues200Response",
    ]
    parse_schema(schema)


def test_include_response_records_fails_for_unmatched_selector() -> None:
    with pytest.raises(InvalidOpenApiError, match="DoesNotExist"):
        convert_openapi_to_avro(
            _doc(),
            GenerationOptions(
                namespace="com.example.filtered",
                root_name="FilteredEnvelope",
                include_response_records=("DoesNotExist",),
            ),
        )


def test_include_response_records_can_select_nested_response_explicitly() -> None:
    schema = convert_openapi_to_avro(
        _doc(),
        GenerationOptions(
            namespace="com.example.filtered",
            root_name="FilteredEnvelope",
            include_status_codes=("200", "default"),
            include_response_records=("VenuesAttributes",),
        ),
    )

    assert _data_branch_names(schema) == ["GetApiVenuesAttributes200Response"]
    parse_schema(schema)


def test_cli_include_response_records_filters_referenced_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "filtered.openapi.json"
    output_path = tmp_path / "schema.avsc"
    references_dir = tmp_path / "references"
    input_path.write_text(json.dumps(_doc()), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(input_path),
            "--namespace",
            "com.example.filtered",
            "--rootname",
            "FilteredEnvelope",
            "--include-status-codes",
            "200,default",
            "--include-response-records",
            "Venues,MatchParticipants",
            "--output",
            str(output_path),
            "--references-output-dir",
            str(references_dir),
            "--root-subject",
            "sts.abc.def.avro-value",
        ],
    )

    assert result.exit_code == 0, result.output
    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert _data_branch_names(schema) == [
        "GetApiMatchParticipants200Response",
        "GetApiVenues200Response",
    ]

    manifest = json.loads((references_dir / "manifest.json").read_text(encoding="utf-8"))
    fullnames = [entry["fullname"] for entry in manifest]
    assert "com.example.filtered.GetApiTeams200Response" not in fullnames
    assert fullnames == [
        "com.example.filtered.Operation",
        "com.example.filtered.EntityType",
        "com.example.filtered.Person",
        "com.example.filtered.GetApiMatchParticipants200Response",
        "com.example.filtered.Address",
        "com.example.filtered.GetApiVenues200Response",
        "com.example.filtered.FilteredEnvelope",
    ]
    assert manifest[-1]["subject"] == "sts.abc.def.avro-value"
