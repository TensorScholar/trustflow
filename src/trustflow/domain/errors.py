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


class ExportRecoveryRequiredError(TrustFlowError):
    """The export artifact committed, but final audit acknowledgement requires recovery."""

    def __init__(self, operation_id: str, output_path: str) -> None:
        self.operation_id = operation_id
        self.output_path = output_path
        super().__init__(
            f"export committed but audit finalization failed; operation={operation_id}; "
            f"output={output_path}; run export-recovery-scan and recover-export"
        )


class IntegrityError(TrustFlowError):
    """Evidence or audit data failed integrity validation."""
