import logfire

from portkey_ai import createHeaders, PORTKEY_GATEWAY_URL
from langchain_openai import ChatOpenAI

from app.config import settings


# =========================================================
# Portkey Saved Configuration
# =========================================================
#
# IMPORTANT:
# We use a Saved Config from Portkey instead of defining
# the gateway configuration inline.
#
# The value should look like:
#
#     pc-xxxxxxxxxxxxxxxx
#
# The Saved Config contains:
# - Fallback strategy
# - Retry policy
# - Primary model
# - Secondary/fallback model
# - Caching configuration
#
PORTKEY_CONFIG = settings.PORTKEY_CONFIG_SLUG


# =========================================================
# LangChain / Portkey LLM
# =========================================================
#
# This function creates a LangChain ChatOpenAI instance
# that sends requests through the Portkey Gateway.
#
# Portkey is responsible for:
# - Model routing
# - Fallback
# - Retries
# - Caching
#
# The application only references the Saved Config slug.
#
def get_langchain_llm(feature: str = "rag") -> ChatOpenAI:
    """
    Return a Portkey-backed LangChain LLM.

    The actual routing, fallback, retry, and caching
    behavior is managed by the Portkey Saved Config.
    """

    logfire.info(
        "Initializing Portkey-backed LLM",
        feature=feature,
        config=PORTKEY_CONFIG,
    )

    return ChatOpenAI(
        # Portkey API key used for authentication.
        api_key=settings.PORTKEY_API_KEY,

        # Send the OpenAI-compatible request through
        # the Portkey Gateway instead of directly to OpenAI.
        base_url=PORTKEY_GATEWAY_URL,

        # Primary model/target.
        #
        # The Groq slug is resolved by Portkey.
        model=f"@{settings.GROQ_SLUG}/openai/gpt-oss-120b",

        # Deterministic responses are preferred for RAG.
        temperature=0,

        # Portkey-specific headers.
        #
        # The "config" value references the Saved Config
        # instead of sending an inline configuration.
        default_headers=createHeaders(
            api_key=settings.PORTKEY_API_KEY,
            config=PORTKEY_CONFIG,

            # Metadata helps identify requests in Portkey.
            metadata={
                "feature": feature,
                "_user": "rag-system",
                "environment": "production",
            },
        ),
    )


# =========================================================
# Portkey Cache Status
# =========================================================
#
# Extract the cache status from the underlying response.
#
# Possible result:
#
#     HIT  -> Response came from Portkey cache
#     MISS -> Response was not served from cache
#
# Different Portkey/LangChain versions may expose the
# underlying HTTP response using different attributes.
#
def extract_cache_status(response) -> str:
    """
    Extract Portkey cache status from the native response.

    Returns:
        "HIT"  -> response served from cache
        "MISS" -> response was not served from cache
    """

    # Possible locations of the raw HTTP response.
    possible_response_attrs = (
        "_raw_response",
        "_response",
        "_http_response",
    )

    for attr in possible_response_attrs:

        # Try to get the underlying response object.
        raw_response = getattr(
            response,
            attr,
            None,
        )

        if raw_response is None:
            continue

        # Extract HTTP headers.
        headers = getattr(
            raw_response,
            "headers",
            {},
        )

        # Portkey exposes cache information through
        # the x-portkey-cache-status header.
        status = headers.get(
            "x-portkey-cache-status",
            "",
        )

        if status:
            return status.upper()

    # If no cache header was found, assume MISS.
    return "MISS"