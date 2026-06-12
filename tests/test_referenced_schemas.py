from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from openapi_get_avro.cli import app
from openapi_get_avro.converter import convert_openapi_to_referenced_avro
from openapi_get_avro.models import GenerationOptions

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_referenced_schema_set_uses_dependency_registration_order() -> None:
    schema_set = convert_openapi_to_referenced_avro(
        load_json("minimal.openapi.json"),
        GenerationOptions(namespace="com.example.sports", root_name="SportsEnvelope"),
    )

    assert schema_set.bundled_schema == load_json("expected-minimal.avsc")
    assert [artifact.fullname for artifact in schema_set.artifacts] == [
        "com.example.sports.Operation",
        "com.example.sports.EntityType",
        "com.example.sports.Venue",
        "com.example.sports.GetMatchResponse",
        "com.example.sports.SportsEnvelope",
    ]

    artifacts = {artifact.fullname: artifact for artifact in schema_set.artifacts}
    response = artifacts["com.example.sports.GetMatchResponse"]
    assert response.schema["namespace"] == "com.example.sports"
    assert response.schema["fields"][-1]["type"] == [
        "null",
        "com.example.sports.Venue",
    ]
    assert [reference.name for reference in response.references] == ["com.example.sports.Venue"]

    root = artifacts["com.example.sports.SportsEnvelope"]
    assert [reference.name for reference in root.references] == [
        "com.example.sports.Operation",
        "com.example.sports.EntityType",
        "com.example.sports.GetMatchResponse",
    ]
    assert root.schema["fields"][-1]["type"] == ["com.example.sports.GetMatchResponse"]


def test_cli_writes_bundled_schema_and_confluent_references(tmp_path: Path) -> None:
    runner = CliRunner()
    bundled_output = tmp_path / "schema.avsc"
    references_dir = tmp_path / "references"

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
            str(bundled_output),
            "--references-output-dir",
            str(references_dir),
            "--reference-subject-template",
            "{fullname}",
            "--root-subject",
            "sts.abc.def.avro-value",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(bundled_output.read_text(encoding="utf-8")) == load_json(
        "expected-minimal.avsc"
    )

    manifest = json.loads((references_dir / "manifest.json").read_text(encoding="utf-8"))
    assert [entry["subject"] for entry in manifest] == [
        "com.example.sports.Operation",
        "com.example.sports.EntityType",
        "com.example.sports.Venue",
        "com.example.sports.GetMatchResponse",
        "sts.abc.def.avro-value",
    ]
    assert manifest[-1]["references"] == [
        {
            "name": "com.example.sports.Operation",
            "subject": "com.example.sports.Operation",
            "version": "latest",
        },
        {
            "name": "com.example.sports.EntityType",
            "subject": "com.example.sports.EntityType",
            "version": "latest",
        },
        {
            "name": "com.example.sports.GetMatchResponse",
            "subject": "com.example.sports.GetMatchResponse",
            "version": "latest",
        },
    ]

    response = json.loads(
        (references_dir / "com.example.sports.GetMatchResponse.avsc").read_text(encoding="utf-8")
    )
    assert response["fields"][-1]["type"] == ["null", "com.example.sports.Venue"]
