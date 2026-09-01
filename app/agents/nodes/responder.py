import logfire
from app.agents.state import AgentState
from app.gateway import portkey_client, extract_cache_status



def generate_node(state: AgentState):
    """
    Generates the final response using:

    - Conversation history for conversational queries.
    - Retrieved enterprise knowledge-base context for RAG queries.
    - Intent-aware reasoning for knowledge and decision-support requests.

    Uses the native Portkey client so cache status can be detected
    and surfaced in the UI.
    """

    query = state["current_query"]

    # Build conversation history
    history_str = ""

    for msg in state["messages"][:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = (
        state["messages"][-1]["content"]
        if state["messages"]
        else ""
    )

    # ---------------------------------------------------------
    # Conversational / Memory response
    # ---------------------------------------------------------

    if query == "CONVERSATIONAL":

        logfire.info(
            "Generating conversational response using conversation memory."
        )

        prompt = f"""
You are a friendly and helpful AI Assistant.

Answer the user's latest message using the conversation history
when relevant.

CONVERSATION HISTORY:

{history_str}

LATEST USER MESSAGE:

"{user_msg}"

Instructions:

1. Answer naturally, clearly, and concisely.
2. Use the conversation history when the user refers to previous messages.
3. Maintain continuity with the conversation.
4. Do not invent information that is not present in the conversation.
5. Do not assume external or enterprise knowledge.
6. Answer only what the user is asking.
"""

    # ---------------------------------------------------------
    # Enterprise RAG response
    # ---------------------------------------------------------

    else:

        logfire.info(
            "Generating enterprise RAG response."
        )

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
You are the Response Generation Agent of an Enterprise Agentic RAG system.

Your task is to generate the final answer to the user's latest question.

You have access to:

- Conversation history
- Retrieved enterprise knowledge-base context

Your answer must be accurate, grounded, useful, and directly address
the user's question.

--------------------------------------------------
RETRIEVED KNOWLEDGE
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

1. Use the retrieved knowledge as the PRIMARY source for factual claims.

2. Only state facts that are supported by the retrieved context or are
   clearly established in the conversation.

3. NEVER fabricate:
   - Facts
   - Numbers
   - Dates
   - Policies
   - Procedures
   - Technical configurations
   - Events
   - Sources

4. Do not rely on general knowledge when the retrieved context does not
   support the answer.

5. If the retrieved context does not contain enough information, clearly
   say:

   "The available knowledge base does not provide enough information
   to answer this confidently."

6. Never fill missing information with assumptions.

--------------------------------------------------
CONVERSATION CONTEXT
--------------------------------------------------

Use the conversation history to understand:

- Follow-up questions
- "it", "this", "that", "they", etc.
- Previously mentioned technologies
- Previously mentioned products
- Previously mentioned entities
- Previous requirements or constraints

Conversation history can help understand the question, but it must NOT
be used to fabricate missing factual information.

--------------------------------------------------
MULTI-SOURCE REASONING
--------------------------------------------------

If the retrieved context contains information from multiple sources:

- Combine relevant evidence when necessary.
- Identify relationships between the sources.
- Do not assume unrelated documents support each other.
- If sources contradict each other, explicitly mention the conflict.
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

Use the retrieved enterprise evidence to support your response.

Clearly distinguish between:

FACT:
Information directly supported by the retrieved context.

INFERENCE:
A conclusion derived from multiple pieces of retrieved evidence.

RECOMMENDATION:
A suggested action based on the available evidence.

Never present an inference or recommendation as a documented fact.

--------------------------------------------------
ANSWER QUALITY
--------------------------------------------------

1. Answer the actual user's question.
2. Be direct and concise.
3. Provide enough explanation to make the answer useful.
4. Do not simply repeat the retrieved documents.
5. Use bullet points or numbered steps when appropriate.
6. Preserve important technical terms, names, versions, and constraints.
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