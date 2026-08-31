import time
import logfire
from flashrank import Ranker,RerankRequest

# Lazy initialization

_ranker = None

def _get_ranker()->Ranker:
    """ Initializes the FlashRank engine lazily.
    FlashRank uses a local ONNX model for fast semantic reranking.
    """
    global _ranker
    if _ranker is None:
        logfire.info("🧠 Initializing FlashRank Model locally...")
        
        try:
            # Use a specific cache directory
            # to avoid permission issues in production
            _ranker = Ranker(cache_dir="/tmp/flashrank")
        except Exception:
            _ranker=Ranker()
    return _ranker



def rerank_documents(
    query: str,
    documents: list[str],
    top_n: int = 5
) -> list[str]:
    """
    Re-ranks retrieved documents based on their semantic
    relevance to the user's query.

    Qdrant performs the initial vector search.
    FlashRank then re-scores those results using a
    cross-encoder model and returns the most relevant ones.
    """

    if not documents:
        return []

    start_time = time.time()

    logfire.info(
        f"📡 [Reranker] Sending {len(documents)} "
        "docs to FlashRank..."
    )

    try:
        ranker = _get_ranker()

        # FlashRank expects passages with an id and text
        passages = [
            {
                "id": i,
                "text": doc
            }
            for i, doc in enumerate(documents)
        ]

        request = RerankRequest(
            query=query,
            passages=passages
        )

        results = ranker.rerank(request)

        # Results are already sorted by semantic score
        reranked_docs = []

        for res in results[:top_n]:
            reranked_docs.append(
                res["text"]
            )

        duration = time.time() - start_time

        top_score = (
            results[0]["score"]
            if results
            else "N/A"
        )

        logfire.info(
            f"✅ [Reranker] Done in {duration:.2f}s. "
            f"Top semantic score: {top_score}"
        )

        return reranked_docs

    except Exception as e:

        logfire.error(
            f"❌ [Reranker] Semantic Reranking Failed: {e}"
        )

        # Fallback to original Qdrant ranking
        return documents[:top_n]