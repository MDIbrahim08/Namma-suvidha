"""Test-only email notification providers.

OWNER: Ibrahim

`TestEmailProvider` logs the full structured payload with prefix
`[TEST EMAIL — NOT DELIVERED]`, appends the message to an in-memory outbox
inspectable by tests, and returns `DeliveryResult(ok=True, ...)`.
`FailingEmailProvider` simulates delivery failure without raising.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.modules.government.interfaces import DeliveryResult

logger = logging.getLogger("namma_suvidha.government.email")


@dataclass
class SentEmailMessage:
    recipient: str
    subject: str
    body: str
    payload: dict[str, Any]
    sent_at: datetime


class TestEmailProvider:
    __test__ = False

    def __init__(self) -> None:
        self.outbox: list[SentEmailMessage] = []

    def clear(self) -> None:
        self.outbox.clear()

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        payload: dict[str, Any],
    ) -> DeliveryResult:
        now = datetime.now(UTC)
        logger.info(
            "[TEST EMAIL — NOT DELIVERED] to=%s subject=%s payload=%s",
            recipient,
            subject,
            payload,
        )
        self.outbox.append(
            SentEmailMessage(
                recipient=recipient,
                subject=subject,
                body=body,
                payload=payload,
                sent_at=now,
            )
        )
        return DeliveryResult(
            ok=True,
            provider_message="[TEST EMAIL — NOT DELIVERED] stored in test outbox",
            sent_at=now,
        )


class FailingEmailProvider:
    """Test helper that always reports delivery failure without raising."""

    def __init__(self, reason: str = "Simulated SMTP transport failure") -> None:
        self.reason = reason

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        payload: dict[str, Any],
    ) -> DeliveryResult:
        logger.warning(
            "[TEST EMAIL — FAILED] to=%s subject=%s reason=%s",
            recipient,
            subject,
            self.reason,
        )
        return DeliveryResult(
            ok=False,
            provider_message=self.reason,
            sent_at=None,
        )
