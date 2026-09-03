import logfire

from langchain_groq import ChatGroq
from nemoguardrails import RailsConfig, LLMRails

from app.config import settings

from app.guardrails.colang_rules import (
    COLANG_CONTENT,
    YAML_CONTENT,
    RAIL_INDICATORS,
)

_rails: LLMRails | None = None


def initialize_rails() -> None:
    """
    Initialize the NeMo Guardrails singleton.

    Guardrails use a lightweight Groq model for:
    - Greeting
    - Farewell
    - Capability questions
    - Off-topic detection
    - Jailbreak detection

    The heavier LLM remains dedicated to the Agentic RAG pipeline.
    """

    global _rails

    if _rails is not None:
        logfire.info("🛡️ NeMo Guardrails already initialised.")
        return

    guard_llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="openai/gpt-oss-20b",
        temperature=0,
    )

    config = RailsConfig.from_content(
        colang_content=COLANG_CONTENT,
        yaml_content=YAML_CONTENT,
    )

    _rails = LLMRails(
        config=config,
        llm=guard_llm,
    )

    logfire.info(
        "🛡️ NeMo Guardrails initialised.",
        model="openai/gpt-oss-20b",
    )


def guard(message: str) -> tuple[bool, str | None]:
    """
    Run a user message through NeMo Guardrails.

    Returns:
        (True, response)  -> guardrail fired
        (False, None)     -> continue to LangGraph / RAG
    """

    if _rails is None:
        logfire.warning(
            "⚠️ Guardrails not initialised — skipping gate."
        )
        return False, None

    if not message or not message.strip():
        logfire.warning(
            "⚠️ Empty user message received."
        )
        return False, None

    message = message.strip()

    with logfire.span("🛡️ Guardrails Check"):

        try:
            # NeMo expects a list of messages.
            result = _rails.generate(
                messages=[
                    {
                        "role": "user",
                        "content": message,
                    }
                ]
            )

            logfire.debug(
                "Guardrails raw result received.",
                result=repr(result),
            )

            if isinstance(result, dict):
                content = result.get("content", "")
            else:
                content = str(result)

            content = content.strip()

            # Check whether the response corresponds
            # to one of our predefined guardrail actions.
            fired_indicator = next(
                (
                    indicator
                    for indicator in RAIL_INDICATORS
                    if indicator.lower() in content.lower()
                ),
                None,
            )

            if fired_indicator:
                logfire.info(
                    "🛡️ Guardrail fired.",
                    query=message[:100],
                    indicator=fired_indicator,
                )

                return True, content

            logfire.info(
                "✅ Guardrails passed.",
                query=message[:100],
            )

            return False, None

        except Exception as e:

            # IMPORTANT:
            # Don't silently convert Guardrails errors into
            # "passed" requests during development.
            logfire.error(
                "❌ Guardrails execution failed.",
                error=str(e),
                error_type=type(e).__name__,
            )

            raise


async def guard_async(message: str) -> tuple[bool, str | None]:
    """Asynchronous version of :func:`guard` for FastAPI request handlers."""

    if _rails is None:
        logfire.warning("⚠️ Guardrails not initialised — skipping gate.")
        return False, None

    if not message or not message.strip():
        logfire.warning("⚠️ Empty user message received.")
        return False, None

    message = message.strip()

    with logfire.span("🛡️ Guardrails Check"):
        try:
            result = await _rails.generate_async(
                messages=[{"role": "user", "content": message}]
            )

            if isinstance(result, dict):
                content = result.get("content", "")
            else:
                content = str(result)

            content = content.strip()
            fired_indicator = next(
                (
                    indicator
                    for indicator in RAIL_INDICATORS
                    if indicator.lower() in content.lower()
                ),
                None,
            )

            if fired_indicator:
                logfire.info(
                    "🛡️ Guardrail fired.",
                    query=message[:100],
                    indicator=fired_indicator,
                )
                return True, content

            logfire.info("✅ Guardrails passed.", query=message[:100])
            return False, None

        except Exception as e:
            logfire.error(
                "❌ Guardrails execution failed.",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
