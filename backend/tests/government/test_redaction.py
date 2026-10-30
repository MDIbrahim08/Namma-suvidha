"""Tests for `redact_responsible_party` contact-field redaction."""

from app.modules.government.domain import ResponsibleParty, redact_responsible_party


def test_redacts_contact_fields_for_citizen_and_anonymous() -> None:
    party = ResponsibleParty(
        name="Ramesh Kumar",
        organization="BBMP Sanitation",
        role_title="Supervisor",
        email="ramesh@example.org",
        phone="+91-80-22220001",
        verified=True,
    )

    citizen_view = redact_responsible_party(party, "citizen")
    assert citizen_view is not None
    assert citizen_view.name == "Ramesh Kumar"
    assert citizen_view.organization == "BBMP Sanitation"
    assert citizen_view.email is None
    assert citizen_view.phone is None

    anon_view = redact_responsible_party(party, None)
    assert anon_view is not None
    assert anon_view.email is None
    assert anon_view.phone is None


def test_preserves_contact_fields_for_government_and_admin() -> None:
    party = ResponsibleParty(
        name="Ramesh Kumar",
        organization="BBMP Sanitation",
        email="ramesh@example.org",
        phone="+91-80-22220001",
        verified=True,
    )

    gov_view = redact_responsible_party(party, "government")
    assert gov_view is not None
    assert gov_view.email == "ramesh@example.org"
    assert gov_view.phone == "+91-80-22220001"

    admin_view = redact_responsible_party(party, {"admin"})
    assert admin_view is not None
    assert admin_view.email == "ramesh@example.org"

