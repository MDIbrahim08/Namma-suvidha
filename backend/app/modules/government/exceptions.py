"""Domain exceptions for Government Monitoring.

OWNER: Ibrahim
"""


class GovernmentDomainError(Exception):
    """Base domain error with HTTP status and machine code."""

    status_code: int = 400
    code: str = "government_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ResourceNotFoundError(GovernmentDomainError):
    status_code = 404
    code = "http_404"


class IllegalIssueTransitionError(GovernmentDomainError):
    status_code = 409
    code = "illegal_issue_transition"


class MissingVerifiedRecipientError(GovernmentDomainError):
    status_code = 422
    code = "missing_verified_recipient"


class InvalidTransitionNoteError(GovernmentDomainError):
    status_code = 422
    code = "transition_note_required"


class UnsupportedNotificationChannelError(GovernmentDomainError):
    status_code = 422
    code = "unsupported_notification_channel"


class GovernmentSchemaPendingError(RuntimeError):
    """Raised by the SQL repository skeleton while Shubham's ORM models are pending."""

