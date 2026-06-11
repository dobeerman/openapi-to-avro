from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from openapi_get_avro.cli import app

FIXTURES = Path(__file__).parent / "fixtures"


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
