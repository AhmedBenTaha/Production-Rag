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
You are an intelligent RAG Assistant Planner.

Analyze the conversation history and the latest user message.

CONVERSATION HISTORY:
{history}

LATEST MESSAGE:
"{user_message}"

Your task is to decide whether the latest message can be answered
using the conversation context or requires information from the
knowledge base.

Rules:

1. If the latest message is a greeting, casual conversation, or a question
   that can be answered using ONLY the conversation history,
   output exactly:

CONVERSATIONAL

2. If the latest message requires factual information, technical information,
   documentation, company information, procedures, policies, or any knowledge
   that may exist in the knowledge base, generate a clear and concise search
   query for retrieval.

3. Do NOT restrict retrieval to any specific topic or domain.
   The knowledge base may contain information about ANY subject.

4. If you are unsure whether the answer exists in the conversation history,
   prefer retrieval.

Output ONLY one of:

CONVERSATIONAL

OR

A refined search query.
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