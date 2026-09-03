import os

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import Optional

from app.agents.graph import rag_agent
from app.guardrails import initialize_rails, guard_async


# ---------------------------------------------------------
# Environment & Observability
# ---------------------------------------------------------

load_dotenv()

logfire.configure(
    token=os.getenv("LOGFIRE_TOKEN")
)


# ---------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------

app = FastAPI(
    title="Enterprise Agentic RAG API"
)


# ---------------------------------------------------------
# Startup
# ---------------------------------------------------------

@app.on_event("startup")
def startup_event():
    initialize_rails()


# ---------------------------------------------------------
# Request Model
# ---------------------------------------------------------

class QueryRequest(BaseModel):
    q: str
    thread_id: Optional[str] = "default_user"


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Enterprise LangGraph RAG API is live."
    }


# ---------------------------------------------------------
# Graph Visualization
# ---------------------------------------------------------

@app.get("/graph")
def get_graph_image():
    try:
        png_bytes = (
            rag_agent
            .get_graph()
            .draw_mermaid_png()
        )

        return Response(
            content=png_bytes,
            media_type="image/png",
        )

    except Exception as e:
        return {
            "error": f"Could not generate graph image: {e}"
        }


# ---------------------------------------------------------
# RAG Query
# ---------------------------------------------------------

@app.post("/query")
async def query(request: QueryRequest):

    q = request.q
    thread_id = request.thread_id

    initial_state = {
        "messages": [
            {
                "role": "user",
                "content": q,
            }
        ],
        "current_query": q,
        "documents": [],
        "plan": ["Start"],
        "status": "Initializing Graph...",
    }

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    try:

        # -------------------------------------------------
        # 1. Guardrails
        # -------------------------------------------------

        rail_fired, rail_response = await guard_async(q)

        if rail_fired:

            logfire.info(
                "🛡️ Request blocked by guardrails",
                thread=thread_id,
            )

            return {
                "question": q,
                "answer": rail_response,
                "thought_process": [
                    "Intent: Guardrails Fired",
                    "Retrieval: Skipped",
                ],
                "status": "Blocked by guardrails.",
                "sources": [],
            }

        # -------------------------------------------------
        # 2. Agentic RAG
        # -------------------------------------------------

        final_output = await rag_agent.ainvoke(
            initial_state,
            config=config,
        )

        # -------------------------------------------------
        # 3. Response
        # -------------------------------------------------

        return {
            "question": q,
            "answer": final_output.get("final_answer"),
            "thought_process": final_output.get("plan"),
            "status": final_output.get("status"),
            "sources": final_output.get("documents", []),
        }

    except Exception as e:

        logfire.error(
            "❌ Backend Execution Failed.",
            error=str(e),
            error_type=type(e).__name__,
        )

        return {
            "question": q,
            "answer": (
                "I apologize, but I encountered an internal "
                "error while processing your request. "
                "Please try again later."
            ),
            "thought_process": [
                "Error encountered during execution."
            ],
            "status": "error",
            "sources": [],
        }