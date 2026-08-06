class TrustFlowError(Exception):
    """Base error for expected TrustFlow failures."""


class UnsafeDocumentError(TrustFlowError):
    """Document failed safety validation."""


class InvalidQuestionnaireError(TrustFlowError):
    """Questionnaire is structurally valid but unusable."""


class UnsupportedFormatError(TrustFlowError):
    """No parser or exporter supports the format."""


class NotFoundError(TrustFlowError):
    """Entity does not exist."""


class InvalidTransitionError(TrustFlowError):
    """Workflow transition is not valid."""


class UnsafeExportError(TrustFlowError):
    """Export destination or payload failed safety validation."""


class IntegrityError(TrustFlowError):
    """Evidence or audit data failed integrity validation."""
