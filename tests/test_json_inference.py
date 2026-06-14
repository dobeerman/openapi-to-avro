from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastavro import parse_schema
from typer.testing import CliRunner

from openapi_get_avro.cli import app
from openapi_get_avro.exceptions import JsonInferenceError
from openapi_get_avro.json_inferer import JsonInferenceOptions, infer_json_to_avro


def test_infers_required_optional_nested_and_array_fields() -> None:
    samples = [
        {
            "id": 1,
            "name": "Alpha",
            "active": True,
            "venue": {"id": "v1", "capacity": 100},
            "tags": ["sport", "live"],
        },
        {
            "id": 2,
            "name": None,
            "active": False,
            "venue": {"id": "v2"},
            "tags": ["sport"],
        },
        {
            "id": 3,
            "active": True,
            "venue": None,
            "tags": [],
        },
    ]

    schema = infer_json_to_avro(
        samples,
        JsonInferenceOptions(namespace="com.example.events", name="Event"),
    )

    assert schema == {
        "type": "record",
        "namespace": "com.example.events",
        "name": "Event",
        "fields": [
            {"name": "id", "type": "long"},
            {"name": "name", "type": ["null", "string"], "default": None},
            {"name": "active", "type": "boolean"},
            {
                "name": "venue",
                "type": [
                    "null",
                    {
                        "type": "record",
                        "name": "EventVenue",
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "capacity", "type": ["null", "long"], "default": None},
                        ],
                    },
                ],
                "default": None,
            },
            {"name": "tags", "type": {"type": "array", "items": "string"}},
        ],
    }
    parse_schema(schema)


def test_rejects_mixed_field_types() -> None:
    samples = [{"id": 1}, {"id": "1"}]

    with pytest.raises(JsonInferenceError, match=r"Incompatible types for Event\.id"):
        infer_json_to_avro(samples, JsonInferenceOptions(namespace="com.example", name="Event"))


def test_infers_uuid_logical_type_for_string_fields() -> None:
    samples = [
        {"transmission_id": "93df767c-8664-49e1-a621-ac67b95006bc"},
        {"transmission_id": "1870f6b0-2a5f-4142-a113-c1c20f35c06b"},
    ]

    schema = infer_json_to_avro(
        samples,
        JsonInferenceOptions(namespace="com.example", name="Event"),
    )

    assert schema["fields"] == [
        {
            "name": "transmission_id",
            "type": {"type": "string", "logicalType": "uuid"},
        }
    ]
    parse_schema(schema)


def test_infers_optional_uuid_logical_type() -> None:
    samples = [
        {"transmission_id": "93df767c-8664-49e1-a621-ac67b95006bc"},
        {"transmission_id": None},
        {},
    ]

    schema = infer_json_to_avro(
        samples,
        JsonInferenceOptions(namespace="com.example", name="Event"),
    )

    assert schema["fields"] == [
        {
            "name": "transmission_id",
            "type": ["null", {"type": "string", "logicalType": "uuid"}],
            "default": None,
        }
    ]
    parse_schema(schema)


def test_keeps_mixed_uuid_and_non_uuid_strings_as_string() -> None:
    samples = [
        {"external_id": "93df767c-8664-49e1-a621-ac67b95006bc"},
        {"external_id": "not-a-uuid"},
    ]

    schema = infer_json_to_avro(
        samples,
        JsonInferenceOptions(namespace="com.example", name="Event"),
    )

    assert schema["fields"] == [{"name": "external_id", "type": "string"}]
    parse_schema(schema)


def test_enforce_timestamp_infers_iso_temporal_strings_as_timestamp_millis() -> None:
    samples = [
        {
            "business_date": "2026-06-05",
            "timestamp": "2026-06-05T21:00:52.1400000Z",
        },
        {
            "business_date": "2026-06-06",
            "timestamp": "2026-06-05T21:00:53.1400000Z",
        },
    ]

    schema = infer_json_to_avro(
        samples,
        JsonInferenceOptions(
            namespace="com.example",
            name="Event",
            enforce_timestamp=True,
        ),
    )

    timestamp_type = {"type": "long", "logicalType": "timestamp-millis"}
    assert schema["fields"] == [
        {"name": "business_date", "type": timestamp_type},
        {"name": "timestamp", "type": timestamp_type},
    ]
    parse_schema(schema)


def test_rejects_all_null_field() -> None:
    samples = [{"name": None}, {"name": None}]

    with pytest.raises(JsonInferenceError, match="all observed values are null"):
        infer_json_to_avro(samples, JsonInferenceOptions(namespace="com.example", name="Event"))


def test_rejects_all_empty_arrays() -> None:
    samples = [{"tags": []}, {"tags": []}]

    with pytest.raises(JsonInferenceError, match="all arrays are empty"):
        infer_json_to_avro(samples, JsonInferenceOptions(namespace="com.example", name="Event"))


def test_infers_disjoint_object_fields_as_optional() -> None:
    samples = [{"home": "A"}, {"away": "B"}]

    schema = infer_json_to_avro(
        samples, JsonInferenceOptions(namespace="com.example", name="Event")
    )

    assert schema["fields"] == [
        {"name": "home", "type": ["null", "string"], "default": None},
        {"name": "away", "type": ["null", "string"], "default": None},
    ]


def test_infers_populated_and_empty_nested_object_fields_as_optional() -> None:
    samples = [
        {"player": {"data": {"left_shoulder": {"x": 1.0, "y": 2.0, "z": 3.0}}}},
        {"player": {"data": {}}},
    ]

    schema = infer_json_to_avro(
        samples, JsonInferenceOptions(namespace="com.example", name="Event")
    )

    player_field = schema["fields"][0]
    player_record = player_field["type"]
    data_field = player_record["fields"][0]
    data_record = data_field["type"]
    assert data_record["fields"][0] == {
        "name": "left_shoulder",
        "type": [
            "null",
            {
                "type": "record",
                "name": "EventPlayerDataLeftShoulder",
                "fields": [
                    {"name": "x", "type": "double"},
                    {"name": "y", "type": "double"},
                    {"name": "z", "type": "double"},
                ],
            },
        ],
        "default": None,
    }


def test_reuses_identical_record_shapes_when_enabled() -> None:
    samples = [
        {
            "left": {"x": 1.0, "y": 2.0, "z": 3.0},
            "right": {"x": 4.0, "y": 5.0, "z": 6.0},
        }
    ]

    schema = infer_json_to_avro(
        samples,
        JsonInferenceOptions(
            namespace="com.example",
            name="Event",
            reuse_record_shapes=True,
        ),
    )

    assert schema == {
        "type": "record",
        "namespace": "com.example",
        "name": "Event",
        "fields": [
            {
                "name": "left",
                "type": {
                    "type": "record",
                    "name": "Position",
                    "fields": [
                        {"name": "x", "type": "double"},
                        {"name": "y", "type": "double"},
                        {"name": "z", "type": "double"},
                    ],
                },
            },
            {"name": "right", "type": "Position"},
        ],
    }
    parse_schema(schema)


def test_reuse_record_shapes_keeps_default_expanded_output() -> None:
    samples = [
        {
            "left": {"x": 1.0, "y": 2.0, "z": 3.0},
            "right": {"x": 4.0, "y": 5.0, "z": 6.0},
        }
    ]

    schema = infer_json_to_avro(
        samples,
        JsonInferenceOptions(namespace="com.example", name="Event"),
    )

    assert schema["fields"][0]["type"]["name"] == "EventLeft"
    assert schema["fields"][1]["type"]["name"] == "EventRight"
    parse_schema(schema)


def test_rejects_all_empty_objects() -> None:
    samples = [{}, {}]

    with pytest.raises(JsonInferenceError, match="objects have no fields"):
        infer_json_to_avro(samples, JsonInferenceOptions(namespace="com.example", name="Event"))


def test_cli_infer_json_writes_schema(tmp_path: Path) -> None:
    input_path = tmp_path / "samples.json"
    output_path = tmp_path / "Event.avsc"
    input_path.write_text(
        json.dumps(
            [
                {"id": 1, "name": "Alpha"},
                {"id": 2},
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "infer-json",
            str(input_path),
            "--name",
            "Event",
            "--namespace",
            "com.example.events",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "type": "record",
        "namespace": "com.example.events",
        "name": "Event",
        "fields": [
            {"name": "id", "type": "long"},
            {"name": "name", "type": ["null", "string"], "default": None},
        ],
    }


def test_cli_infer_json_reports_human_readable_error(tmp_path: Path) -> None:
    input_path = tmp_path / "samples.json"
    input_path.write_text(json.dumps([{"id": 1}, {"id": "1"}]), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "infer-json",
            str(input_path),
            "--name",
            "Event",
            "--namespace",
            "com.example.events",
        ],
    )

    assert result.exit_code == 1
    assert f"Failed to infer Avro schema for {input_path}" in result.output
    assert "Incompatible types for Event.id" in result.output


def test_cli_infer_json_reuse_record_shapes_option(tmp_path: Path) -> None:
    input_path = tmp_path / "samples.json"
    output_path = tmp_path / "Event.avsc"
    input_path.write_text(
        json.dumps(
            [
                {
                    "left": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "right": {"x": 4.0, "y": 5.0, "z": 6.0},
                }
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "infer-json",
            str(input_path),
            "--name",
            "Event",
            "--namespace",
            "com.example",
            "--reuse-record-shapes",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    assert actual["fields"][0]["type"]["name"] == "Position"
    assert actual["fields"][1]["type"] == "Position"


def test_cli_infer_json_enforce_timestamp_option(tmp_path: Path) -> None:
    input_path = tmp_path / "samples.json"
    output_path = tmp_path / "Event.avsc"
    input_path.write_text(
        json.dumps(
            [
                {"timestamp": "2026-06-05T21:00:52.1400000Z"},
                {"timestamp": "2026-06-05T21:00:53.1400000Z"},
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "infer-json",
            str(input_path),
            "--name",
            "Event",
            "--namespace",
            "com.example",
            "--enforce-timestamp",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    assert actual["fields"] == [
        {
            "name": "timestamp",
            "type": {"type": "long", "logicalType": "timestamp-millis"},
        }
    ]
