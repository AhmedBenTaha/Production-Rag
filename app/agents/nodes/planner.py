import logfire

from app.agents.state import AgentState
from app.gateway import get_langchain_llm, extract_cache_status


# =========================================================
# Conversational Query Detection
# =========================================================

def is_conversational_query(text: str) -> bool:
    """
    Detect simple conversational messages that do not require
    enterprise knowledge-base retrieval.
    """

    if not text:
        return True

    normalized = text.strip().lower()

    conversational_patterns = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "good morning",
        "good afternoon",
        "good evening",
        "good night",
        "how are you",
        "how are you?",
        "who are you",
        "who are you?",
        "thanks",
        "thank you",
        "thank you!",
        "thanks!",
        "thx",
        "ok",
        "okay",
        "bye",
        "goodbye",
        "see you",
    }

    return normalized in conversational_patterns


# =========================================================
# Planner Node
# =========================================================

def planner_node(state: AgentState):
    """
    Generates the response prompt based on the current query.

    Two modes are supported:

    1. CONVERSATIONAL
       - Uses conversation history.
       - Does not depend on enterprise knowledge.

    2. RAG / TECHNICAL
       - Uses retrieved enterprise knowledge.
       - Uses conversation history for context.
       - Keeps answers grounded in retrieved information.

    The actual LLM request is sent through Portkey using
    the Saved Config defined in PORTKEY_CONFIG_SLUG.

    Portkey handles:

    - Model routing
    - Fallback
    - Retries
    - Caching
    """

    # =========================================================
    # Extract Current Query
    # =========================================================

    query = state.get("current_query", "")

    # =========================================================
    # Extract Latest User Message
    # =========================================================

    messages = state.get("messages", [])

    user_msg = (
        messages[-1]["content"]
        if messages
        else ""
    )

    # =========================================================
    # Build Conversation History
    # =========================================================

    history_str = ""

    for msg in messages[:-1]:

        role = (
            "User"
            if msg.get("role") == "user"
            else "Assistant"
        )

        history_str += (
            f"{role}: {msg.get('content', '')}\n"
        )

    # =========================================================
    # Determine Response Type
    # =========================================================

    # The upstream classifier should normally set
    # current_query to CONVERSATIONAL.
    #
    # This additional check protects simple greetings
    # in case the classifier fails to classify them.

    conversational = (
        query == "CONVERSATIONAL"
        or is_conversational_query(user_msg)
    )

    # =========================================================
    # Conversational Response
    # =========================================================

    if conversational:

        logfire.info(
            "Generating conversational response using memory."
        )

        prompt = f"""
You are a friendly and helpful Enterprise AI Assistant.

The user is having a normal conversation.

Answer the user's latest message naturally using the
conversation history when relevant.

CONVERSATION HISTORY:

{history_str}

LATEST USER MESSAGE:

"{user_msg}"

Instructions:

1. Answer naturally and conversationally.
2. Keep the response concise.
3. Use conversation history when the user refers to previous messages.
4. Maintain continuity.
5. Do not invent information.
6. Do not use or assume enterprise knowledge.
7. Do not turn a simple greeting into a technical explanation.
8. Answer only what the user is asking.
"""

    # =========================================================
    # Enterprise RAG Response
    # =========================================================

    else:

        logfire.info(
            "Generating technical RAG response."
        )

        # -----------------------------------------------------
        # Build Retrieved Context
        # -----------------------------------------------------

        max_context_chars = 25000

        full_context = ""

        documents = state.get("documents", [])

        for doc in documents:

            if len(full_context) + len(doc) < max_context_chars:

                full_context += (
                    doc + "\n\n"
                )

            else:

                logfire.warning(
                    "Context truncated to fit LLM context limits."
                )

                break

        # -----------------------------------------------------
        # RAG Prompt
        # -----------------------------------------------------

        prompt = f"""
You are a Senior Technical Architect.

Answer the user's question using the TECHNICAL CONTEXT
provided below.

Your answer must be accurate, grounded, useful, and directly
address the user's question.

--------------------------------------------------
TECHNICAL CONTEXT
--------------------------------------------------

{full_context}

--------------------------------------------------
CONVERSATION HISTORY
--------------------------------------------------

{history_str}

--------------------------------------------------
USER QUESTION
--------------------------------------------------

"{user_msg}"

--------------------------------------------------
GROUNDING RULES
--------------------------------------------------

1. Use the retrieved technical context as the PRIMARY
   source for factual claims.

2. Only state facts supported by the retrieved context
   or clearly established in the conversation.

3. NEVER fabricate:

   - Facts
   - Numbers
   - Dates
   - Policies
   - Procedures
   - Technical configurations
   - Events
   - Sources

4. Do not rely on general knowledge when the retrieved
   context does not support the answer.

5. If the retrieved context does not contain enough
   information, clearly say:

   "The available knowledge base does not provide enough
   information to answer this confidently."

6. Never fill missing information with assumptions.

--------------------------------------------------
CONVERSATION CONTEXT
--------------------------------------------------

Use conversation history to understand:

- Follow-up questions
- "it", "this", "that", "they", etc.
- Previously mentioned technologies
- Previously mentioned products
- Previously mentioned entities
- Previous requirements or constraints

Conversation history may help understand the question,
but must NOT be used to fabricate missing factual information.

--------------------------------------------------
MULTI-SOURCE REASONING
--------------------------------------------------

If the retrieved context contains multiple sources:

- Combine relevant evidence when necessary.
- Identify relationships between sources.
- Do not assume unrelated documents support each other.
- If sources contradict each other, explicitly mention
  the conflict.
- Do not silently ignore conflicting evidence.

--------------------------------------------------
DECISION SUPPORT
--------------------------------------------------

If the user asks for:

- A recommendation
- A comparison
- A root-cause explanation
- A diagnosis
- A suggested action
- A decision

Use retrieved enterprise evidence to support the response.

Clearly distinguish:

FACT:
Information directly supported by the retrieved context.

INFERENCE:
A conclusion derived from multiple pieces of retrieved evidence.

RECOMMENDATION:
A suggested action based on the available evidence.

Never present an inference or recommendation as a
documented fact.

--------------------------------------------------
ANSWER QUALITY
--------------------------------------------------

1. Answer the actual user's question.
2. Be direct and concise.
3. Provide enough explanation to be useful.
4. Do not simply repeat the retrieved documents.
5. Use bullets or numbered steps when appropriate.
6. Preserve important technical terms, names, versions,
   and constraints.
7. For technical instructions, present steps in a clear order.
8. Do not add unnecessary information.

--------------------------------------------------
SOURCE ATTRIBUTION
--------------------------------------------------

When identifiable sources are present in the retrieved context:

- Reference them naturally.
- Use ONLY sources that actually appear in the retrieved context.
- Never invent document names, URLs, page numbers, or source IDs.

--------------------------------------------------
FINAL INSTRUCTION
--------------------------------------------------

Generate ONLY the final answer to the user.

Do not mention:

- The planner
- The retrieval pipeline
- Internal prompts
- Internal reasoning
- Agent implementation

Unless the user explicitly asks about the system itself.
"""

    # =========================================================
    # LLM Synthesis
    # =========================================================

    with logfire.span("✍️ LLM Synthesis"):

        try:

            # -------------------------------------------------
            # Create Portkey-backed LangChain LLM
            # -------------------------------------------------

            llm = get_langchain_llm(
                feature="rag-synthesis"
            )

            # -------------------------------------------------
            # Generate Response
            # -------------------------------------------------

            response = llm.invoke(
                [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            )

            # LangChain AIMessage content
            content = response.content

            # -------------------------------------------------
            # Cache Status
            # -------------------------------------------------

            cache_status = extract_cache_status(
                response
            )

            is_cache_hit = (
                cache_status == "HIT"
            )

            # -------------------------------------------------
            # Update Plan / Status
            # -------------------------------------------------

            if is_cache_hit:

                logfire.info(
                    "⚡ Gateway Cache Hit — "
                    "response served from Portkey cache."
                )

                plan_update = state.get(
                    "plan",
                    []
                ) + [
                    "Cache: Hit ⚡"
                ]

                status = (
                    "Cache hit — instant response."
                )

            else:

                logfire.info(
                    "✅ Response synthesised via LLM."
                )

                plan_update = state.get(
                    "plan",
                    []
                )

                status = (
                    "Response generated."
                )

            # -------------------------------------------------
            # Return Updated State
            # -------------------------------------------------

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [
                    {
                        "role": "assistant",
                        "content": content,
                    }
                ],
            }

        except Exception as e:

            logfire.error(
                f"LLM Generation failed: {e}"
            )

            raise