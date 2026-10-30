"""Evaluator Authentication, Onboarding, WebAuthn, Private ID Storage,
Admin Verification, and Append-Only Audit Logging module.

OWNER: Ibrahim (integration) + Shabaz (auth/biometrics) + Shubham (schema/cooldowns)
"""

from app.modules.evaluator.auth_interface import (
    EvaluatorAuthProvider,
    SupabaseJwtVerifier,
    VerifiedJwtClaims,
    build_hs256_jwt,
)
from app.modules.evaluator.config import (
    EvaluatorModuleSettings,
    get_evaluator_module_settings,
    validate_evaluator_startup,
)
from app.modules.evaluator.dependencies import (
    EvaluatorServices,
    build_evaluator_services,
    get_evaluator_services,
    require_admin,
    require_approved_evaluator,
    require_authenticated_claims,
    require_evaluator,
)
from app.modules.evaluator.exceptions import EvaluatorDomainError
from app.modules.evaluator.repositories import (
    EvaluatorRepositoryBundle,
    get_evaluator_memory_bundle,
    get_evaluator_repository_bundle,
)
from app.modules.evaluator.service import (
    AdminEvaluatorManagementService,
    EvaluatorOnboardingService,
)
from app.modules.evaluator.storage import (
    EvaluatorDocumentStorageService,
    InMemoryPrivateDocumentStorage,
    detect_and_validate_id_magic_bytes,
    get_private_document_storage,
)
from app.modules.evaluator.webauthn import WebAuthnService

__all__ = [
    "AdminEvaluatorManagementService",
    "EvaluatorAuthProvider",
    "EvaluatorDocumentStorageService",
    "EvaluatorDomainError",
    "EvaluatorModuleSettings",
    "EvaluatorOnboardingService",
    "EvaluatorRepositoryBundle",
    "EvaluatorServices",
    "InMemoryPrivateDocumentStorage",
    "SupabaseJwtVerifier",
    "VerifiedJwtClaims",
    "WebAuthnService",
    "build_evaluator_services",
    "build_hs256_jwt",
    "detect_and_validate_id_magic_bytes",
    "get_evaluator_memory_bundle",
    "get_evaluator_module_settings",
    "get_evaluator_repository_bundle",
    "get_evaluator_services",
    "get_private_document_storage",
    "require_admin",
    "require_approved_evaluator",
    "require_authenticated_claims",
    "require_evaluator",
    "validate_evaluator_startup",
]
