"""
Retriever component for RAG pipeline.
Validates: Requirements 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

from typing import List

from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.models.data_models import RetrievedChunk, SearchResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class Retriever:
    """
    Retrieves relevant chunks from vector store.
    
    Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
    """
    
    DEFAULT_K = 5
    MIN_K = 1
    MAX_K = 20
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        logger.info("Retriever initialized")
    
    def retrieve(
        self, 
        query: str, 
        k: int = DEFAULT_K
    ) -> List[RetrievedChunk]:
        """
        Retrieve top-K relevant chunks for query.
        
        Args:
            query: User query in Vietnamese
            k: Number of chunks to retrieve (1-20)
            
        Returns:
            List of RetrievedChunk sorted by similarity (descending)
            
        Validates: Requirements 8.1, 8.2, 8.3, 8.5
        """
        # Validate K parameter (Req 8.1)
        if k < self.MIN_K or k > self.MAX_K:
            raise ValueError(
                f"K must be between {self.MIN_K} and {self.MAX_K}, got {k}"
            )
        
        logger.info(f"Retrieving chunks", extra={"query": query[:50], "k": k})
        
        # Generate query embedding (Req 8.2)
        query_embedding = self.embedding_service.embed_single(query)
        
        # Search vector store (Req 8.3)
        search_results: List[SearchResult] = self.vector_store.search(
            query_embedding, 
            k=k
        )
        
        # Convert to RetrievedChunk (Req 8.4, 8.5, 8.6)
        retrieved_chunks = []
        for result in search_results:
            retrieved_chunks.append(
                RetrievedChunk(
                    text=result.text,
                    similarity_score=result.similarity_score,
                    metadata=result.metadata
                )
            )
        
        logger.info(
            f"Retrieved {len(retrieved_chunks)} chunks",
            extra={"top_score": retrieved_chunks[0].similarity_score if retrieved_chunks else 0}
        )
        
        return retrieved_chunks
