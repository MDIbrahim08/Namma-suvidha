"""FastAPI dependency container for the Evaluator Authentication & Management module.

OWNER: Ibrahim
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.modules.evaluator.auth_interface import (
    EvaluatorAuthProvider,
    VerifiedJwtClaims,
)
from app.modules.evaluator.config import (
    EvaluatorModuleSettings,
    get_evaluator_module_settings,
    validate_evaluator_startup,
)
from app.modules.evaluator.domain import EvaluatorUserRecord
from app.modules.evaluator.interfaces import (
    EvaluatorClock,
    PrivateDocumentStorageProvider,
    SystemEvaluatorClock,
)
from app.modules.evaluator.repositories import (
    EvaluatorRepositoryBundle,
    get_evaluator_repository_bundle,
)
from app.modules.evaluator.service import (
    AdminEvaluatorManagementService,
    EvaluatorOnboardingService,
)
from app.modules.evaluator.storage import (
    EvaluatorDocumentStorageService,
    get_private_document_storage,
)
from app.modules.evaluator.webauthn import WebAuthnService

_DEFAULT_CLOCK: EvaluatorClock = SystemEvaluatorClock()


def get_evaluator_clock() -> EvaluatorClock:
    return _DEFAULT_CLOCK


@dataclass
class EvaluatorServices:
    repos: EvaluatorRepositoryBundle
    settings: EvaluatorModuleSettings
    clock: EvaluatorClock
    storage: PrivateDocumentStorageProvider
    auth: EvaluatorAuthProvider
    webauthn: WebAuthnService
    documents: EvaluatorDocumentStorageService
    onboarding: EvaluatorOnboardingService
    admin: AdminEvaluatorManagementService


def build_evaluator_services(
    *,
    app_settings: Settings | None = None,
    eval_settings: EvaluatorModuleSettings | None = None,
    repos: EvaluatorRepositoryBundle | None = None,
    clock: EvaluatorClock | None = None,
    storage: PrivateDocumentStorageProvider | None = None,
) -> EvaluatorServices:
    core_cfg = app_settings or get_settings()
    mod_cfg = eval_settings or get_evaluator_module_settings()
    validate_evaluator_startup(core_cfg.APP_ENV, mod_cfg)

    bundle = repos or get_evaluator_repository_bundle(
        mod_cfg.REPOSITORY_BACKEND, app_env=core_cfg.APP_ENV
    )
    clk = clock or get_evaluator_clock()
    doc_store = storage or get_private_document_storage()

    auth_provider = EvaluatorAuthProvider(
        settings=core_cfg, repos=bundle, clock=clk
    )
    webauthn_svc = WebAuthnService(
        repos=bundle, settings=mod_cfg, clock=clk
    )
    doc_svc = EvaluatorDocumentStorageService(
        repos=bundle, storage=doc_store, settings=mod_cfg, clock=clk
    )
    onboarding_svc = EvaluatorOnboardingService(
        repos=bundle, webauthn=webauthn_svc, settings=mod_cfg, clock=clk
    )
    admin_svc = AdminEvaluatorManagementService(
        repos=bundle, settings=mod_cfg, clock=clk
    )

    return EvaluatorServices(
        repos=bundle,
        settings=mod_cfg,
        clock=clk,
        storage=doc_store,
        auth=auth_provider,
        webauthn=webauthn_svc,
        documents=doc_svc,
        onboarding=onboarding_svc,
        admin=admin_svc,
    )


def get_evaluator_services(
    app_settings: Settings = Depends(get_settings),
    eval_settings: EvaluatorModuleSettings = Depends(
        get_evaluator_module_settings
    ),
    clock: EvaluatorClock = Depends(get_evaluator_clock),
) -> EvaluatorServices:
    return build_evaluator_services(
        app_settings=app_settings,
        eval_settings=eval_settings,
        clock=clock,
    )


def require_authenticated_claims(
    request: Request,
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> VerifiedJwtClaims:
    return services.auth.require_authenticated_claims(request)


def require_evaluator(
    request: Request,
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> EvaluatorUserRecord:
    return services.auth.require_evaluator_user(request)


def require_approved_evaluator(
    request: Request,
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> EvaluatorUserRecord:
    return services.auth.require_approved_evaluator_user(request)


def require_admin(
    request: Request,
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> EvaluatorUserRecord:
    return services.auth.require_admin_user(request)

