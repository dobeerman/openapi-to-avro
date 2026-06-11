from __future__ import annotations

import json
from pathlib import Path

from fastavro import parse_schema

from openapi_get_avro.converter import convert_openapi_to_avro
from openapi_get_avro.models import GenerationOptions

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_minimal_openapi_converts_to_expected_avro() -> None:
    openapi_doc = load_json("minimal.openapi.json")
    expected = load_json("expected-minimal.avsc")

    actual = convert_openapi_to_avro(
        openapi_doc,
        GenerationOptions(namespace="com.example.sports", root_name="SportsEnvelope"),
    )

    assert actual == expected
    parse_schema(actual)


def test_conversion_is_deterministic() -> None:
    openapi_doc = load_json("minimal.openapi.json")
    options = GenerationOptions(namespace="com.example.sports", root_name="SportsEnvelope")

    first = convert_openapi_to_avro(openapi_doc, options)
    second = convert_openapi_to_avro(openapi_doc, options)

    assert json.dumps(first, indent=2, ensure_ascii=False) == json.dumps(
        second, indent=2, ensure_ascii=False
    )
