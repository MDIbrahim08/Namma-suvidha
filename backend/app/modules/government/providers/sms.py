"""SMS notification providers (Test and configurable stubs).

OWNER: Ibrahim / Government Automated Notification System

Email is the primary MVP channel; SMS is optional and configurable.
Failures are reported truthfully without pretending delivery succeeded.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.modules.government.interfaces import DeliveryResult

logger = logging.getLogger("namma_suvidha.government.sms")


class SMSProvider(Protocol):
    def send(self, phone: str, message: str) -> DeliveryResult:
        ...


@dataclass
class SentSMSMessage:
    phone: str
    message: str
    sent_at: datetime


class TestSMSProvider:
    __test__ = False

    def __init__(self) -> None:
        self.outbox: list[SentSMSMessage] = []

    def clear(self) -> None:
        self.outbox.clear()

    def send(self, phone: str, message: str) -> DeliveryResult:
        now = datetime.now(UTC)
        logger.info("[TEST SMS — NOT DELIVERED] to=%s message=%s", phone, message)
        self.outbox.append(
            SentSMSMessage(
                phone=phone,
                message=message,
                sent_at=now,
            )
        )
        return DeliveryResult(
            ok=True,
            provider_message="[TEST SMS — NOT DELIVERED] stored in test outbox",
            sent_at=now,
        )


class FailingSMSProvider:
    """Test helper that always reports SMS delivery failure truthfully."""

    def __init__(self, reason: str = "Simulated SMS Gateway timeout or invalid number") -> None:
        self.reason = reason

    def send(self, phone: str, message: str) -> DeliveryResult:
        logger.warning("[TEST SMS — FAILED] to=%s reason=%s", phone, self.reason)
        return DeliveryResult(
            ok=False,
            provider_message=self.reason,
            sent_at=None,
        )

