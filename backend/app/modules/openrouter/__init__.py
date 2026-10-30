"""OpenRouter & Groq AI integration and Voice Feedback Pipeline preparation.

OWNER: Ibrahim (integration & voice feedback pipeline preparation)
COORDINATES WITH: Shubham (official scoring & intelligence owner)
"""

from app.modules.openrouter.client import (
    OpenRouterClientProtocol,
    OpenRouterConfigError,
    OpenRouterError,
    OpenRouterHttpClient,
    OpenRouterPrivacyViolationError,
    OpenRouterProviderError,
    OpenRouterResponseValidationError,
    OpenRouterTimeoutError,
    enforce_openrouter_privacy_guard,
    is_free_openrouter_model,
)
from app.modules.openrouter.groq_client import (
    GroqClientProtocol,
    GroqConfigError,
    GroqError,
    GroqHttpClient,
    GroqProviderError,
    GroqResponseValidationError,
    GroqTimeoutError,
)
from app.modules.openrouter.services import (
    ComplaintUnderstandingService,
    ImageInspectionAnalysisService,
    ImageValidationError,
    MaintenanceEmailDraftingService,
    SpeechTranscriptionService,
    validate_image_upload,
)

__all__ = [
    "ComplaintUnderstandingService",
    "GroqClientProtocol",
    "GroqConfigError",
    "GroqError",
    "GroqHttpClient",
    "GroqProviderError",
    "GroqResponseValidationError",
    "GroqTimeoutError",
    "ImageInspectionAnalysisService",
    "ImageValidationError",
    "MaintenanceEmailDraftingService",
    "OpenRouterClientProtocol",
    "OpenRouterConfigError",
    "OpenRouterError",
    "OpenRouterHttpClient",
    "OpenRouterPrivacyViolationError",
    "OpenRouterProviderError",
    "OpenRouterResponseValidationError",
    "OpenRouterTimeoutError",
    "SpeechTranscriptionService",
    "enforce_openrouter_privacy_guard",
    "is_free_openrouter_model",
    "validate_image_upload",
]
