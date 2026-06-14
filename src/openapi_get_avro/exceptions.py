"""Project-specific exception types."""


class OpenApiAvroError(Exception):
    """Base exception for OpenAPI to Avro conversion failures."""


class UnsupportedSchemaError(OpenApiAvroError):
    """Raised when strict mode finds an unsupported or ambiguous schema construct."""


class InvalidOpenApiError(OpenApiAvroError):
    """Raised when the input document cannot be interpreted as an OpenAPI specification."""


class AvroNameError(OpenApiAvroError):
    """Raised when a valid deterministic Avro name cannot be produced."""


class JsonInferenceError(OpenApiAvroError):
    """Raised when JSON samples cannot be safely inferred as an Avro schema."""
