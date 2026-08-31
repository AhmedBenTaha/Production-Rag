import logfire
from app.agents.state import AgentState
from app.gateway import portkey_client, extract_cache_status


def generate_node(state: AgentState):
    """
    Generates the final response using:
    - Conversation history for conversational queries.
    - Retrieved knowledge-base context for RAG queries.

    Uses the native Portkey client so cache status can be detected
    and surfaced in the UI.
    """

    query = state["current_query"]

    # Build conversation history
    history_str = ""

    for msg in state["messages"][:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    # ---------------------------------------------------------
    # Conversational / Memory response
    # ---------------------------------------------------------
    if query == "CONVERSATIONAL":

        logfire.info(
            "Generating conversational response using conversation memory."
        )

        prompt = f"""
You are a friendly and helpful General AI Assistant.

Answer the user's latest message using the conversation history
when relevant.

CONVERSATION HISTORY:
{history_str}

LATEST USER MESSAGE:
"{user_msg}"

Instructions:
- Answer naturally and clearly.
- Use the conversation history when the user refers to previous messages.
- Do not invent information that is not present in the conversation.
"""

    # ---------------------------------------------------------
    # General RAG response
    # ---------------------------------------------------------
    else:

        logfire.info("Generating general RAG response.")

        max_context_chars = 25000
        full_context = ""

        for doc in state["documents"]:

            if len(full_context) + len(doc) < max_context_chars:
                full_context += doc + "\n\n"

            else:
                logfire.warning(
                    "Context truncated to fit LLM context limits."
                )
                break

        prompt = f"""
You are a helpful General AI Assistant.

Answer the user's question using the retrieved knowledge-base
context provided below.

RETRIEVED CONTEXT:
{full_context}

CONVERSATION HISTORY:
{history_str}

USER QUESTION:
"{user_msg}"

Instructions:
1. Use the retrieved context as the primary source of information.
2. Answer clearly, accurately, and directly.
3. Use conversation history when it provides useful context.
4. Do not invent facts that are not supported by the retrieved context.
5. If the retrieved context does not contain enough information,
   clearly say that the available knowledge base does not provide
   enough information to answer confidently.
6. Do not assume the question is technical; it can be about any subject.
"""

    # ---------------------------------------------------------
    # LLM Generation
    # ---------------------------------------------------------
    with logfire.span("✍️ LLM Synthesis"):

        try:

            response = portkey_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1
            )

            content = response.choices[0].message.content

            # Portkey cache status
            cache_status = extract_cache_status(response)
            is_cache_hit = cache_status == "HIT"

            if is_cache_hit:

                logfire.info(
                    "⚡ Gateway Cache Hit — response served from Portkey cache."
                )

                plan_update = state["plan"] + ["Cache: Hit ⚡"]
                status = "Cache hit — instant response."

            else:

                logfire.info(
                    "✅ Response synthesised via LLM."
                )

                plan_update = state["plan"]
                status = "Response generated."

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [
                    {
                        "role": "assistant",
                        "content": content
                    }
                ]
            }

        except Exception as e:

            logfire.error(
                f"LLM Generation failed: {e}"
            )

            raise