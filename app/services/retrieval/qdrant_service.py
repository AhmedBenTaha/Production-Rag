import logfire
from app.config import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.services.retrieval.embedding import embed_query


client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY
)


def search_knowledge(query:str,limit:int=8):
    """ Performs a high-precision search in the knowledge base. Uses the modern query_points interface. """
    try:
        query_vector = embed_query(query)
        # Using query_points - the modern standard for Qdrant
        response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            limit=limit,
            with_payload=True
        )
        results = [] 
        for res in response.points:
            results.append({ "content": res.payload.get("text", ""),
                            "source": res.payload.get("source", "Unknown"), 
                            "score": res.score }) 
            return results
    
    except Exception as e :
        logfire.error(f"❌ Qdrant Search Failed: {e}") 
        return []