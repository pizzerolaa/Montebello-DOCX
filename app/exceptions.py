class DocumentAppError(Exception):
    """Base application error."""


class InvalidDocumentError(DocumentAppError):
    """The uploaded document is malformed or unsafe."""


class UnsupportedDocumentError(DocumentAppError):
    """The uploaded document type is not supported."""


class MarkerNotFoundError(DocumentAppError):
    """A required Word template marker was not found."""


class ExtractionError(DocumentAppError):
    """Extraction failed."""


class ValidationError(DocumentAppError):
    """Reviewed data did not pass validation."""


class GenerationError(DocumentAppError):
    """Document generation failed."""


class StorageError(DocumentAppError):
    """File storage failed."""

