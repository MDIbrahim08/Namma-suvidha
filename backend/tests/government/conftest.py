"""Shared fixtures for Government Monitoring tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.main import create_app
from app.modules.government.config import (
    GovernmentSettings,
    get_government_settings,
)
from app.modules.government.dependencies import (
    get_clock,
    get_email_provider,
    get_score_provider,
)
from app.modules.government.providers.email import TestEmailProvider
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories import RepositoryBundle, get_memory_bundle
from tests.government.factories import FixedClock


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def memory_repos() -> Iterator[RepositoryBundle]:
    bundle = get_memory_bundle()
    bundle.clear_all()
    yield bundle
    bundle.clear_all()


@pytest.fixture
def score_provider() -> Iterator[IntelligenceScoreProvider]:
    provider = IntelligenceScoreProvider()
    provider.clear_overrides()
    yield provider
    provider.clear_overrides()


@pytest.fixture
def email_outbox() -> Iterator[TestEmailProvider]:
    provider = TestEmailProvider()
    provider.clear()
    yield provider
    provider.clear()


@pytest.fixture
def gov_settings() -> GovernmentSettings:
    return GovernmentSettings()


@pytest.fixture
def gov_client(
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
    email_outbox: TestEmailProvider,
    gov_settings: GovernmentSettings,
) -> Iterator[TestClient]:
    """TestClient authenticated as a `government` role user via dependency_overrides."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "gov-officer-1",
        "roles": ["government"],
    }
    app.dependency_overrides[get_clock] = lambda: fixed_clock
    app.dependency_overrides[get_score_provider] = lambda: score_provider
    app.dependency_overrides[get_email_provider] = lambda: email_outbox
    app.dependency_overrides[get_government_settings] = lambda: gov_settings
    app.dependency_overrides[get_settings] = lambda: Settings(APP_ENV="development")

    with TestClient(app) as client:
        yield client

