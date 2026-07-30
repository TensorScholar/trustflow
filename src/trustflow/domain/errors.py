class TrustFlowError(Exception):
    """Base error."""

class UnsafeDocumentError(TrustFlowError):
    """Document failed safety validation."""

class UnsupportedFormatError(TrustFlowError):
    """No parser or exporter supports the format."""

class NotFoundError(TrustFlowError):
    """Entity does not exist."""

class InvalidTransitionError(TrustFlowError):
    """Workflow transition is not valid."""

class IntegrityError(TrustFlowError):
    """Evidence or audit data failed integrity validation."""
