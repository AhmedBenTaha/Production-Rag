import logfire

from app.agents.state import AgentState
from app.services.retrieval.qdrant_service import search_knowledge
from app.services.retrieval.ranking_service import rerank_documents


def retrieve_node(state: AgentState):
    """
    Performs vector search and semantic reranking
    for general knowledge-base queries.
    """

    query = state["current_query"]

    # ---------------------------------------------------------
    # Vector Retrieval
    # ---------------------------------------------------------
    with logfire.span("🔍 Knowledge Retrieval"):

        logfire.info(
            f"Searching Qdrant for: {query}"
        )

        # Retrieve more candidates first
        raw_results = search_knowledge(
            query,
            limit=15
        )

        logfire.info(
            f"Retrieved {len(raw_results)} "
            "candidates from Vector DB"
        )

        # Extract document content
        doc_contents = [
            doc["content"]
            for doc in raw_results
        ]

        # -----------------------------------------------------
        # Semantic Reranking
        # -----------------------------------------------------
        with logfire.span("⚖️ Semantic Reranking"):

            reranked_contents = rerank_documents(
                query,
                doc_contents,
                top_n=5
            )

            logfire.info(
                "Reranking complete. "
                "Kept top 5 most relevant chunks."
            )

        # -----------------------------------------------------
        # Format Context
        # -----------------------------------------------------
        formatted_docs = [
            f"CONTENT: {doc}"
            for doc in reranked_contents
        ]

    return {
        "documents": formatted_docs,
        "status": "Relevant context retrieved.",
        "plan": state["plan"] + [
            "Context Retrieved"
        ]
    }
