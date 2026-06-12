from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from openapi_get_avro.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def test_cli_generates_expected_schema(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "schema.avsc"

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(FIXTURES / "minimal.openapi.json"),
            "--namespace",
            "com.example.sports",
            "--rootname",
            "SportsEnvelope",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    expected = json.loads((FIXTURES / "expected-minimal.avsc").read_text(encoding="utf-8"))
    actual = json.loads(output.read_text(encoding="utf-8"))
    assert actual == expected


def test_cli_help_exposes_generation_policy_options() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["generate", "--help"],
        env={"COLUMNS": "120"},
        terminal_width=120,
    )

    assert result.exit_code == 0
    help_output = _strip_ansi(result.output)
    assert "--name-strategy" in help_output
    assert "--any-of-policy" in help_output
    assert "--enum-policy" in help_output
    assert "--unknown-object-policy" in help_output
    assert "--include-response-records" in help_output
    assert "--remove-name-suffixes" in help_output
    assert "--field-name-case" in help_output
    assert "--references-output-dir" in help_output
    assert "--references-manifest-output" in help_output
    assert "--reference-subject-template" in help_output
    assert "--root-subject" in help_output


def test_cli_include_status_codes_preserves_requested_order(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "statuses.openapi.json"
    output_path = tmp_path / "schema.avsc"
    input_path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Status API"},
                "paths": {
                    "/thing": {
                        "get": {
                            "operationId": "getThing",
                            "tags": ["Thing"],
                            "responses": {
                                "206": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {"partial": {"type": "boolean"}},
                                            }
                                        }
                                    }
                                },
                                "default": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {"error": {"type": "string"}},
                                            }
                                        }
                                    }
                                },
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {"ok": {"type": "string"}},
                                            }
                                        }
                                    }
                                },
                            },
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(input_path),
            "--namespace",
            "com.example.status",
            "--rootname",
            "StatusEnvelope",
            "--include-status-codes",
            "200,206,default",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    data_field = actual["fields"][-1]
    assert [branch["name"] for branch in data_field["type"]] == [
        "GetThing200Response",
        "GetThing206Response",
        "GetThingDefaultResponse",
    ]


def test_cli_name_strategy_path_overrides_operation_id(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "path-name.openapi.json"
    output_path = tmp_path / "schema.avsc"
    input_path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Path API"},
                "paths": {
                    "/matches/{matchId}/lineups": {
                        "get": {
                            "operationId": "ignoredOperationId",
                            "tags": ["Match"],
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {"id": {"type": "string"}},
                                            }
                                        }
                                    }
                                }
                            },
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(input_path),
            "--namespace",
            "com.example.path",
            "--rootname",
            "PathEnvelope",
            "--name-strategy",
            "path",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    data_field = actual["fields"][-1]
    assert data_field["type"][0]["name"] == "GetMatchesByMatchIdLineupsResponse"


def test_cli_field_name_case_transforms_payload_field_names(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "field-case.openapi.json"
    output_path = tmp_path / "schema.avsc"
    input_path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Field Case API"},
                "paths": {
                    "/lineups": {
                        "get": {
                            "operationId": "getLineup",
                            "tags": ["Lineup"],
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {
                                                    "lineupVersion": {"type": "integer"},
                                                },
                                            }
                                        }
                                    }
                                }
                            },
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(input_path),
            "--namespace",
            "com.example.fieldcase",
            "--rootname",
            "FieldCaseEnvelope",
            "--field-name-case",
            "snake_case",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    data_field = actual["fields"][-1]
    branch = data_field["type"][0]
    assert branch["fields"][0]["name"] == "lineup_version"


def test_cli_rejects_invalid_field_name_case() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(FIXTURES / "minimal.openapi.json"),
            "--namespace",
            "com.example.sports",
            "--rootname",
            "SportsEnvelope",
            "--field-name-case",
            "kebab-case",
        ],
    )

    assert result.exit_code != 0
    error_output = _strip_ansi(result.output)
    assert "--field-name-case must be one of: preserve, snake_case" in error_output
    assert "camelCase, PascalCase" in error_output


def test_cli_rejects_empty_remove_name_suffix() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(FIXTURES / "minimal.openapi.json"),
            "--namespace",
            "com.example.sports",
            "--rootname",
            "SportsEnvelope",
            "--remove-name-suffixes",
            "Dto,",
        ],
    )

    assert result.exit_code != 0
    error_output = _strip_ansi(result.output)
    assert "--remove-name-suffixes cannot contain empty suffixes" in error_output


def test_cli_rejects_invalid_remove_name_suffix() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(FIXTURES / "minimal.openapi.json"),
            "--namespace",
            "com.example.sports",
            "--rootname",
            "SportsEnvelope",
            "--remove-name-suffixes",
            "Dto,!Bad",
        ],
    )

    assert result.exit_code != 0
    error_output = _strip_ansi(result.output)
    assert "--remove-name-suffixes values must be valid Avro name" in error_output
    assert "suffixes: '!Bad'" in error_output


def test_cli_error_message_includes_input_path_and_get_response(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "bad-enum.openapi.json"
    input_path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Bad API"},
                "paths": {
                    "/bad": {
                        "get": {
                            "operationId": "getBad",
                            "tags": ["Bad"],
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {
                                                    "status": {
                                                        "type": "string",
                                                        "enum": ["NOT VALID"],
                                                    }
                                                },
                                            }
                                        }
                                    }
                                }
                            },
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "generate",
            "--input",
            str(input_path),
            "--namespace",
            "com.example.bad",
            "--rootname",
            "BadEnvelope",
        ],
    )

    assert result.exit_code == 1
    assert f"Failed to generate Avro schema for {input_path}" in result.output
    assert "GET /bad response 200" in result.output
    assert "Invalid Avro enum symbol" in result.output
