import logfire

from portkey_ai import Portkey, createHeaders, PORTKEY_GATEWAY_URL
from langchain_openai import ChatOpenAI

from app.config import settings

PORTKEY_CONFIG = settings.PORTKEY_CONFIG_SLUG


# =========================================================
# Production Gateway Configuration
# =========================================================
#
# Primary:
#   openai/gpt-oss-120b
#
# Fallback:
#   openai/gpt-oss-20b
#
# Reliability:
#   - Retry twice on rate-limit / temporary server errors
#   - Automatically fallback to the secondary model if needed
#
# Caching:
#   - Simple cache mode
#
# Routing:
#   - Portkey handles model routing
#   - @slug/model-name is resolved by Portkey
#

GATEWAY_CONFIG = {
    "strategy": {
        "mode": "fallback",
    },

    
    "retry": {
        "attempts": 2,
        "on_status_codes": [
            429,
            503,
        ],
    },

    "targets": [
        {
            "override_params": {
                "model": (
                    f"@{settings.GROQ_SLUG}/"
                    "openai/gpt-oss-120b"
                )
            }
        },
        {
            "override_params": {
                "model": (
                    f"@{settings.GROQ_SLUG_2}/"
                    "openai/gpt-oss-20b"
                )
            }
        },
    ],
}


# =========================================================
# Native Portkey Client
# =========================================================

portkey_client = Portkey(
    api_key=settings.PORTKEY_API_KEY,
    config=GATEWAY_CONFIG,
)


# =========================================================
# LangChain / Portkey LLM
# =========================================================

def get_langchain_llm(feature: str = "rag") -> ChatOpenAI:
    """
    Return a Portkey-backed LangChain LLM.

    Routing, fallback, retry, and caching are handled
    by the Portkey saved configuration.
    """

    logfire.info(
        "Initializing Portkey-backed LLM",
        feature=feature,
        config=PORTKEY_CONFIG,
    )

    return ChatOpenAI(
        api_key=settings.PORTKEY_API_KEY,
        base_url=PORTKEY_GATEWAY_URL,
        model=f"@{settings.GROQ_SLUG}/openai/gpt-oss-120b",
        temperature=0,
        default_headers=createHeaders(
            api_key=settings.PORTKEY_API_KEY,
            config=PORTKEY_CONFIG,
            metadata={
                "feature": feature,
                "_user": "rag-system",
                "environment": "production",
            },
        ),
    )
# =========================================================
# Cache Status
# =========================================================

def extract_cache_status(response) -> str:
    """
    Extract Portkey cache status from the native response.

    Portkey may expose the underlying HTTP response through
    different internal attributes depending on the SDK version.

    Returns:
        "HIT"  -> response served from cache
        "MISS" -> response was not served from cache
    """

    possible_response_attrs = (
        "_raw_response",
        "_response",
        "_http_response",
    )

    for attr in possible_response_attrs:

        raw_response = getattr(
            response,
            attr,
            None,
        )

        if raw_response is None:
            continue

        headers = getattr(
            raw_response,
            "headers",
            {},
        )

        status = headers.get(
            "x-portkey-cache-status",
            "",
        )

        if status:

            return status.upper()

    return "MISS"

