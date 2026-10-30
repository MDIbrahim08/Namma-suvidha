"""Domain exceptions for the Evaluator Authentication & Management module.

OWNER: Ibrahim
"""


class EvaluatorDomainError(Exception):
    """Base domain error with HTTP status and machine-readable code."""

    status_code: int = 400
    code: str = "evaluator_error"

    def __init__(
        self,
        detail: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class EvaluatorNotFoundError(EvaluatorDomainError):
    status_code = 404
    code = "evaluator_not_found"


class EvaluatorAuthenticationError(EvaluatorDomainError):
    status_code = 401
    code = "evaluator_unauthenticated"


class EvaluatorForbiddenError(EvaluatorDomainError):
    status_code = 403
    code = "evaluator_forbidden"


class EvaluatorNotApprovedError(EvaluatorDomainError):
    status_code = 403
    code = "evaluator_not_approved"


class EvaluatorConflictError(EvaluatorDomainError):
    status_code = 409
    code = "evaluator_conflict"


class IllegalEvaluatorStateTransitionError(EvaluatorDomainError):
    status_code = 409
    code = "illegal_evaluator_state_transition"


class EvaluatorValidationError(EvaluatorDomainError):
    status_code = 422
    code = "evaluator_validation_error"


class WebAuthnVerificationError(EvaluatorDomainError):
    status_code = 401
    code = "webauthn_verification_failed"


class WebAuthnLegacyReRegistrationRequiredError(EvaluatorDomainError):
    status_code = 409
    code = "webauthn_legacy_re_registration_required"


class DocumentStorageError(EvaluatorDomainError):
    status_code = 422
    code = "document_storage_error"


class AuditLogImmutableError(EvaluatorDomainError):
    status_code = 403
    code = "audit_log_immutable"


class EvaluatorSchemaPendingError(EvaluatorDomainError):
    """Raised when SQL persistence is requested before Shubham & Shabaz's
    SQL migration (`20261031_evaluator_auth_schema.sql`) is applied, or when
    `APP_ENV=production` is configured with `EVAL_REPOSITORY_BACKEND=memory`.
    """

    status_code = 503
    code = "evaluator_sql_persistence_unavailable"

