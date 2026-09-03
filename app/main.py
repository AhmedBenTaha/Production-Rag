import os

import logfire

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import Optional

from app.agents.graph import rag_agent

# Guardrails disabled temporarily
# from app.guardrails import initialize_rails, guard_async


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

# Guardrails disabled temporarily
# @app.on_event("startup")
# def startup_event():
#     initialize_rails()


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
# RAG Query - Streaming
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

        # Guardrails disabled temporarily
        #
        # rail_fired, rail_response = await guard_async(q)
        #
        # if rail_fired:
        #     logfire.info(
        #         "🛡️ Request blocked by guardrails",
        #         thread=thread_id,
        #     )
        #
        #     return {
        #         "question": q,
        #         "answer": rail_response,
        #         "thought_process": [
        #             "Intent: Guardrails Fired",
        #             "Retrieval: Skipped",
        #         ],
        #         "status": "Blocked by guardrails.",
        #         "sources": [],
        #     }

        # -------------------------------------------------
        # 2. Agentic RAG - Streaming
        # -------------------------------------------------

        final_output = None

        async for chunk in rag_agent.astream(
            initial_state,
            config=config,
        ):
            logfire.info(
                "📡 RAG stream chunk received",
                chunk_type=type(chunk).__name__,
            )

            final_output = chunk

        # -------------------------------------------------
        # 3. Response
        # -------------------------------------------------

        if final_output is None:
            return {
                "question": q,
                "answer": None,
                "thought_process": [],
                "status": "No output generated.",
                "sources": [],
            }

        # LangGraph may return node-based updates from astream()
        if isinstance(final_output, dict):

            # Try to extract final answer directly
            answer = final_output.get("final_answer")

            # If final_answer is nested inside a node update
            if answer is None:
                for value in final_output.values():

                    if isinstance(value, dict):
                        if value.get("final_answer") is not None:
                            answer = value["final_answer"]

            # Plan
            plan = final_output.get("plan", [])

            if not plan:
                for value in final_output.values():
                    if isinstance(value, dict) and value.get("plan"):
                        plan = value["plan"]
                        break

            # Documents
            documents = final_output.get("documents", [])

            if not documents:
                for value in final_output.values():
                    if isinstance(value, dict) and value.get("documents"):
                        documents = value["documents"]
                        break

            # Status
            status = final_output.get(
                "status",
                "Completed"
            )

            return {
                "question": q,
                "answer": answer,
                "thought_process": plan,
                "status": status,
                "sources": documents,
            }

        return {
            "question": q,
            "answer": str(final_output),
            "thought_process": [],
            "status": "Completed",
            "sources": [],
        }

    except Exception as e:
        import traceback

        print("\n" + "=" * 80, flush=True)
        print("❌ BACKEND ERROR", flush=True)
        print(f"ERROR TYPE: {type(e).__name__}", flush=True)
        print(f"ERROR: {e}", flush=True)
        print("=" * 80, flush=True)
        traceback.print_exc()

        logfire.error(
            "❌ Backend Execution Failed.",
            error=str(e),
            error_type=type(e).__name__,
        )

        return {
            "question": request.q,
            "answer": "I apologize, but I encountered an internal error while processing your request. Please try again later.",
            "thought_process": ["Error encountered during execution."],
            "status": "error",
            "sources": [],
        }