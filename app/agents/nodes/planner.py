from app.agents.state import AgentState
import logfire



def planner_node(state:AgentState):
    """
    The Planner determines whether the latest message can be answered
    conversationally or requires retrieval from the knowledge base.
    """
    history=""
    for msg in state["messages"][:-1]:
        role = "User" if msg["role"]=="user" else "Assistant" 
        history += f"{role}: {msg['content']}\n"
    user_message = state["messages"][-1]["content"] if state["messages"] else ""
    
    prompt = f"""
You are the Planner Agent of an Enterprise Agentic RAG system.

Your task is to analyze the ENTIRE conversation history and the latest
user message, then decide whether the request can be answered from
conversation context or requires retrieving information from the
enterprise knowledge base.

CONVERSATION HISTORY:
{history}

LATEST USER MESSAGE:
"{user_message}"

--------------------------------------------------
DECISION RULES
--------------------------------------------------

1. CONVERSATIONAL

Return exactly:

CONVERSATIONAL

when the latest message:

- Is a greeting, farewell, thanks, or casual conversation.
- Can be answered completely using information already present in the
  conversation history.
- Refers to something explicitly discussed earlier and does not require
  any external or enterprise knowledge.

Examples:
- "Hi"
- "Thanks"
- "What was my previous question?"
- "Can you explain your last answer again?"

--------------------------------------------------

2. KNOWLEDGE RETRIEVAL

If the latest message requires information that may exist in the
enterprise knowledge base, generate a clear and optimized search query.

This includes:

- Technical questions
- Company information
- Internal documentation
- Policies and procedures
- Product documentation
- Troubleshooting
- Configuration instructions
- Best practices
- Incident information
- Reports
- Any factual information that cannot be confidently answered from
  the conversation history alone.

Do NOT restrict retrieval to a specific domain or technology.

The knowledge base may contain information about ANY subject.

--------------------------------------------------

3. FOLLOW-UP QUESTIONS

Pay close attention to references such as:

- "What about this?"
- "How do I configure it?"
- "Does this apply to them?"
- "Why did that happen?"
- "What is the difference?"
- "Can you explain that?"

Use the conversation history to resolve what the user is referring to.

If the question requires knowledge that is not contained in the
conversation, generate a retrieval query that includes the necessary
context from the previous messages.

--------------------------------------------------

4. RETRIEVAL PREFERENCE

When uncertain whether the conversation history contains enough
information to answer the question, ALWAYS prefer retrieval.

Do not assume that information is correct or complete just because
something similar appeared earlier in the conversation.

--------------------------------------------------

5. SEARCH QUERY GENERATION

When retrieval is required:

- Rewrite the user's question into a concise, precise search query.
- Preserve important entities, technologies, product names, versions,
  dates, error messages, and constraints.
- Include relevant context from previous messages when necessary.
- Remove conversational filler.
- Do not answer the question.
- Do not add information that was not provided by the user or found
  in the conversation.

The generated query should be optimized for semantic and keyword
retrieval from an enterprise knowledge base.

--------------------------------------------------
OUTPUT FORMAT
--------------------------------------------------

Return ONLY ONE of the following:

CONVERSATIONAL

OR

A refined search query.

Do not include explanations, labels, reasoning, markdown, or additional text.

"""
    with logfire.span("🧠 Planner Decision"):
        decision = llm.invoke(prompt).content.strip()

        if decision.upper().rstrip(".") == "CONVERSATIONAL":
            decision = "CONVERSATIONAL"

        logfire.info(f"Intent identified: {decision}")

    if decision == "CONVERSATIONAL":
        return {
            "current_query": "CONVERSATIONAL",
            "status": "Handling conversationally (using memory)...",
            "plan": [
                "Intent: Conversational/Memory",
                "Retrieval: Skipped"
            ]
        }

    return {
        "current_query": decision,
        "status": f"Knowledge retrieval needed. Searching for: {decision}",
        "plan": [
            "Intent: Knowledge Retrieval",
            f"Search Term: {decision}"
        ]
    }