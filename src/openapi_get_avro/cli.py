"""Command-line interface for OpenAPI GET to Avro generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from ruamel.yaml import YAML

from .converter import convert_openapi_to_avro
from .exceptions import OpenApiAvroError
from .models import GenerationOptions

app = typer.Typer(
    no_args_is_help=True, help="Convert OpenAPI GET responses to Avro envelope schema"
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
) -> None:
    """Generate an Avro envelope schema from GET responses in an OpenAPI document."""
    try:
        openapi_doc = _load_document(input)
        options = GenerationOptions(
            namespace=namespace,
            root_name=rootname,
            include_status_codes=tuple(
                code.strip() for code in include_status_codes.split(",") if code.strip()
            ),
            content_type=content_type,
            strict=strict,
        )
        avro_schema = convert_openapi_to_avro(openapi_doc, options)
        rendered = json.dumps(avro_schema, indent=2, ensure_ascii=False) + "\n"
        if output is None:
            typer.echo(rendered, nl=False)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
    except (OpenApiAvroError, json.JSONDecodeError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


# Allows the console script to expose the command directly while still supporting `python -m`.
if __name__ == "__main__":
    app()
