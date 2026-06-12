"""Command-line interface for OpenAPI GET to Avro generation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any, TypeVar

import typer
from ruamel.yaml import YAML

from .converter import convert_openapi_to_avro
from .exceptions import OpenApiAvroError
from .models import (
    AnyOfPolicy,
    EnumPolicy,
    FieldNameCase,
    GenerationOptions,
    NameStrategy,
    UnknownObjectPolicy,
)

app = typer.Typer(
    no_args_is_help=True, help="Convert OpenAPI GET responses to Avro envelope schema"
)

TChoice = TypeVar("TChoice", bound=str)

AVRO_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NAME_STRATEGIES: tuple[NameStrategy, ...] = ("operationId", "path")
FIELD_NAME_CASES: tuple[FieldNameCase, ...] = (
    "preserve",
    "snake_case",
    "camelCase",
    "PascalCase",
)
ANY_OF_POLICIES: tuple[AnyOfPolicy, ...] = ("fail", "union")
ENUM_POLICIES: tuple[EnumPolicy, ...] = ("fail", "string", "sanitize")
UNKNOWN_OBJECT_POLICIES: tuple[UnknownObjectPolicy, ...] = (
    "fail",
    "map",
    "string",
    "empty-record",
)


@app.callback()
def main() -> None:
    """Convert OpenAPI GET responses to Avro envelope schema."""


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        loaded = YAML(typ="safe").load(text)
    else:
        loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise typer.BadParameter("Input document must be a JSON/YAML object")
    return loaded


def _parse_choice(value: str, allowed: tuple[TChoice, ...], option_name: str) -> TChoice:
    normalized = value.strip()
    if normalized in allowed:
        return normalized
    choices = ", ".join(allowed)
    raise typer.BadParameter(f"{option_name} must be one of: {choices}")


def _parse_status_codes(value: str) -> tuple[str, ...]:
    status_codes = tuple(code.strip() for code in value.split(",") if code.strip())
    if not status_codes:
        raise typer.BadParameter("--include-status-codes must include at least one status code")
    return status_codes


def _parse_name_suffixes(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    suffixes = tuple(suffix.strip() for suffix in value.split(","))
    if any(not suffix for suffix in suffixes):
        raise typer.BadParameter("--remove-name-suffixes cannot contain empty suffixes")
    invalid_suffixes = [suffix for suffix in suffixes if not AVRO_NAME_RE.fullmatch(suffix)]
    if invalid_suffixes:
        invalid = ", ".join(repr(suffix) for suffix in invalid_suffixes)
        raise typer.BadParameter(
            f"--remove-name-suffixes values must be valid Avro name suffixes: {invalid}"
        )
    return suffixes


@app.command()
def generate(
    input: Annotated[
        Path,
        typer.Option("--input", "-i", exists=True, readable=True, help="OpenAPI JSON/YAML file"),
    ],
    namespace: Annotated[
        str, typer.Option("--namespace", help="Avro namespace for generated records")
    ],
    rootname: Annotated[str, typer.Option("--rootname", help="Root Avro record name")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output .avsc file, defaults to stdout")
    ] = None,
    include_status_codes: Annotated[
        str, typer.Option("--include-status-codes", help="Comma-separated response codes")
    ] = "200",
    content_type: Annotated[
        str, typer.Option("--content-type", help="Response content type to include")
    ] = "application/json",
    strict: Annotated[
        bool, typer.Option("--strict/--lenient", help="Fail on ambiguous constructs")
    ] = True,
    name_strategy: Annotated[
        str,
        typer.Option(
            "--name-strategy",
            help="Response naming strategy: operationId or path",
        ),
    ] = "operationId",
    field_name_case: Annotated[
        str,
        typer.Option(
            "--field-name-case",
            help="Payload field name case: preserve, snake_case, camelCase, or PascalCase",
        ),
    ] = "preserve",
    any_of_policy: Annotated[
        str,
        typer.Option("--any-of-policy", help="anyOf handling policy: fail or union"),
    ] = "fail",
    enum_policy: Annotated[
        str,
        typer.Option("--enum-policy", help="Enum handling policy: fail, string, or sanitize"),
    ] = "fail",
    unknown_object_policy: Annotated[
        str,
        typer.Option(
            "--unknown-object-policy",
            help="Unknown object policy: fail, map, string, or empty-record",
        ),
    ] = "fail",
    remove_name_suffixes: Annotated[
        str,
        typer.Option(
            "--remove-name-suffixes",
            help="Comma-separated generated Avro named-type suffixes to remove",
        ),
    ] = "",
) -> None:
    """Generate an Avro envelope schema from GET responses in an OpenAPI document."""
    try:
        openapi_doc = _load_document(input)
        options = GenerationOptions(
            namespace=namespace,
            root_name=rootname,
            include_status_codes=_parse_status_codes(include_status_codes),
            content_type=content_type,
            strict=strict,
            name_strategy=_parse_choice(name_strategy, NAME_STRATEGIES, "--name-strategy"),
            field_name_case=_parse_choice(
                field_name_case,
                FIELD_NAME_CASES,
                "--field-name-case",
            ),
            any_of_policy=_parse_choice(any_of_policy, ANY_OF_POLICIES, "--any-of-policy"),
            enum_policy=_parse_choice(enum_policy, ENUM_POLICIES, "--enum-policy"),
            unknown_object_policy=_parse_choice(
                unknown_object_policy,
                UNKNOWN_OBJECT_POLICIES,
                "--unknown-object-policy",
            ),
            remove_name_suffixes=_parse_name_suffixes(remove_name_suffixes),
        )
        avro_schema = convert_openapi_to_avro(openapi_doc, options)
        rendered = json.dumps(avro_schema, indent=2, ensure_ascii=False) + "\n"
        if output is None:
            typer.echo(rendered, nl=False)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
    except (OpenApiAvroError, json.JSONDecodeError, OSError, ValueError) as exc:
        typer.echo(f"Failed to generate Avro schema for {input}: {exc}", err=True)
        raise typer.Exit(1) from exc


# Allows the console script to expose the command directly while still supporting `python -m`.
if __name__ == "__main__":
    app()
