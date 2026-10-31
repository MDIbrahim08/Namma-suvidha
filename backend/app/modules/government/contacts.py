"""Official Contact Directory and Ward-to-Authority Mapping.

OWNER: Ibrahim / Government Automated Notification System

Stores and resolves official recipient contacts for city corporations and wards.
Contacts are loaded from configuration (JSON/environment) and never hardcoded
in business logic.
"""

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.government.enums import NotificationChannel

logger = logging.getLogger("namma_suvidha.government.contacts")


class OfficialContact(BaseModel):
    id: str
    recipient_name: str
    department_designation: str
    city_corporation: str = "Bruhat Bengaluru Mahanagara Palike (BBMP)"
    ward_mappings: list[str] = Field(default_factory=list)
    official_email: str
    office_phone: str | None = None
    notification_channel: NotificationChannel = NotificationChannel.email
    active: bool = True
    is_escalation_supervisor: bool = False


class OfficialContactDirectory:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self._contacts: list[OfficialContact] = []
        if config_path is None:
            # Default to the bundled official_contacts.json
            config_path = Path(__file__).parent / "data" / "official_contacts.json"
        self._load_from_path(Path(config_path))

    def _load_from_path(self, path: Path) -> None:
        if not path.is_file():
            logger.warning("Official contacts config file not found: %s", path)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._contacts = [OfficialContact.model_validate(c) for c in data]
                logger.info("Loaded %d official contacts from %s", len(self._contacts), path)
        except Exception as e:
            logger.error("Failed to load official contacts config from %s: %s", path, e)

    def list_contacts(self, active_only: bool = True) -> list[OfficialContact]:
        if active_only:
            return [c for c in self._contacts if c.active]
        return list(self._contacts)

    def get_contact_by_id(self, contact_id: str) -> OfficialContact | None:
        for c in self._contacts:
            if c.id == contact_id:
                return c
        return None

    def resolve_contact(
        self,
        ward: str | None,
        city_corporation: str = "Bruhat Bengaluru Mahanagara Palike (BBMP)",
        for_escalation: bool = False,
    ) -> OfficialContact | None:
        """Resolve the official contact responsible for a facility ward or zone.
        
        Matches active contacts by:
        1. Exact/substring ward match if ward is specified.
        2. Escalation supervisor flag if `for_escalation` is True.
        3. Wildcard `*` corporation-wide fallback.
        """
        active_contacts = [c for c in self._contacts if c.active]

        if for_escalation:
            for c in active_contacts:
                if c.is_escalation_supervisor:
                    return c

        if ward:
            clean_ward = ward.strip().lower()
            # 1. Direct or partial ward match
            for c in active_contacts:
                for mapping in c.ward_mappings:
                    mapping_clean = mapping.strip().lower()
                    if mapping_clean == "*" or c.is_escalation_supervisor:
                        continue
                    if mapping_clean in clean_ward or clean_ward in mapping_clean:
                        return c

        # 2. Fallback to corporation-wide active contact / escalation authority
        for c in active_contacts:
            if "*" in c.ward_mappings or c.is_escalation_supervisor:
                return c

        return active_contacts[0] if active_contacts else None

    def add_contact(self, contact: OfficialContact) -> None:
        self._contacts.append(contact)


_DIRECTORY_INSTANCE: OfficialContactDirectory | None = None


def get_official_contact_directory(config_path: str | Path | None = None) -> OfficialContactDirectory:
    global _DIRECTORY_INSTANCE
    if _DIRECTORY_INSTANCE is None:
        _DIRECTORY_INSTANCE = OfficialContactDirectory(config_path)
    return _DIRECTORY_INSTANCE

