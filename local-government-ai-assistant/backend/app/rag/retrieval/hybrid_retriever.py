"""
Hybrid Retriever: Combines Dense (Vector) + Sparse (BM25) Search.

Hybrid search combines:
1. Dense retrieval: Semantic similarity (vector embeddings)
2. Sparse retrieval: Keyword matching (BM25)

Fusion method: Reciprocal Rank Fusion (RRF)
- Paper: "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods"
- Formula: RRF_score(d) = sum(1 / (k + rank_i(d))) for all rankings i
"""

from typing import List, Optional, Tuple
import numpy as np
from pathlib import Path

from app.rag.retrieval.retriever import Retriever
from app.rag.retrieval.bm25s_index import BM25SIndex
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.models.data_models import RetrievedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


class HybridRetriever(Retriever):
    """
    Hybrid retrieval combining dense and sparse methods.
    
    Architecture:
    Query → [Vector Search] ──┐
            [BM25 Search]   ──┤→ [RRF Fusion] → Top-K Results
    
    Benefits:
    - Vector: Captures semantic meaning, synonyms, paraphrasing
    - BM25: Captures exact terms, proper nouns, technical terms
    - RRF: Combines rankings without score normalization issues
    
    Validates: Enhanced Requirements 8.1-8.6
    """
    
    # RRF constant (recommended value from paper)
    RRF_K = 60
    
    # Cosine-similarity threshold applied to vector candidates before fusion.
    # NOTE: RRF scores (~1/60) and cross-encoder logits use a different scale,
    # so this value must NOT be applied to fused/reranked results.
    MIN_SIMILARITY_THRESHOLD = 0.25
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        alpha: float = 0.6,
        min_similarity: float = MIN_SIMILARITY_THRESHOLD,
        use_reranking: bool = False,
        bm25s_persist_dir: Optional[str] = None
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            embedding_service: Embedding service for vector search
            vector_store: Vector store for similarity search
            alpha: Weight for vector search (0-1)
                   0.6 = 60% weight on semantic, 40% on keyword
                   Recommended: 0.5-0.7 for balanced retrieval
            min_similarity: Minimum similarity score threshold
            use_reranking: Whether to apply cross-encoder reranking
            bm25s_persist_dir: Directory to persist BM25S index
        """
        super().__init__(embedding_service, vector_store)
        # Persistence is opt-in: tests and ad-hoc instances must never
        # overwrite the production BM25 index on disk.
        self.bm25_index = BM25SIndex(
            persist_dir=Path(bm25s_persist_dir) if bm25s_persist_dir else None
        )
        self.alpha = alpha
        self.min_similarity = min_similarity
        self.use_reranking = use_reranking
        
        # Initialize reranker if enabled (will be set later)
        self.reranker = None
        if use_reranking:
            # Lazy loading - import only if needed
            from app.rag.retrieval.reranker import Reranker
            self.reranker = Reranker()
        
        logger.info(
            "HybridRetriever initialized with BM25S",
            extra={
                "alpha": alpha,
                "min_similarity": min_similarity,
                "rrf_k": self.RRF_K,
                "reranking_enabled": use_reranking,
                "bm25s_persist_dir": bm25s_persist_dir
            }
        )
    
    def index_documents(self, chunks: List[RetrievedChunk]) -> None:
        """
        Build BM25S index for hybrid search.
        
        Call this after documents are loaded into vector store.
        Index is automatically saved to disk if persistence is enabled.
        
        Args:
            chunks: All chunks that have been indexed
        """
        logger.info(f"Building BM25S index for {len(chunks)} chunks")
        self.bm25_index.index_chunks(chunks)
        logger.info("BM25S index ready for hybrid search")
    
    def retrieve(
        self, 
        query: str, 
        k: int = 5
    ) -> List[RetrievedChunk]:
        """
        Hybrid retrieval with RRF fusion.
        
        Process:
        1. Retrieve candidates from both vector and BM25 (k*3 each)
        2. Fuse using Reciprocal Rank Fusion
        3. Apply reranking if enabled
        4. Filter by similarity threshold
        5. Return top-K results
        
        Args:
            query: User query in Vietnamese
            k: Number of final results
            
        Returns:
            Fused and filtered chunks, sorted by RRF score
        """
        # Validate K parameter
        if k < self.MIN_K or k > self.MAX_K:
            raise ValueError(
                f"K must be between {self.MIN_K} and {self.MAX_K}, got {k}"
            )
        
        logger.info(
            "Hybrid retrieval started",
            extra={
                "query": query[:50],
                "k": k,
                "alpha": self.alpha,
                "threshold": self.min_similarity
            }
        )
        
        # Retrieve more candidates for better fusion
        candidate_k = min(k * 3, self.MAX_K)
        
        # 1. Dense retrieval (vector/semantic search)
        logger.debug("Performing vector search")
        vector_results = super().retrieve(query, k=candidate_k)

        # Filter cosine similarity BEFORE fusion. The threshold is meaningless
        # after RRF (score ~1/60) or reranking (cross-encoder logit).
        vector_count_before_filter = len(vector_results)
        vector_results = [
            chunk for chunk in vector_results
            if chunk.similarity_score >= self.min_similarity
        ]

        # 2. Sparse retrieval (BM25/keyword search)
        logger.debug("Performing BM25 search")
        bm25_results = self.bm25_index.search(query, k=candidate_k)
        
        # 3. Reciprocal Rank Fusion
        logger.debug("Fusing results with RRF")
        fused_results = self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            k=k
        )
        
        # 4. Apply reranking if enabled (ordering only, no score filtering)
        if self.reranker and fused_results:
            logger.debug("Applying cross-encoder reranking")
            rerank_k = min(k * 2, len(fused_results))
            fused_results = self.reranker.rerank(
                query,
                fused_results,
                top_k=rerank_k
            )
        
        final_results = fused_results[:k]
        
        logger.info(
            "Hybrid retrieval completed",
            extra={
                "vector_count_raw": vector_count_before_filter,
                "vector_count_filtered": len(vector_results),
                "bm25_count": len(bm25_results),
                "fused_count": len(fused_results),
                "final_count": len(final_results),
                "top_score": final_results[0].similarity_score if final_results else 0
            }
        )
        
        return final_results
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[Tuple],
        k: int
    ) -> List[RetrievedChunk]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF formula:
        RRF_score(d) = α × 1/(K + rank_vector(d)) + (1-α) × 1/(K + rank_bm25(d))
        
        Where:
        - K = 60 (constant from RRF paper)
        - rank(d) = position of document d in ranking (0-indexed)
        - α = weight for vector search
        
        Args:
            vector_results: Results from vector search (already sorted)
            bm25_results: Results from BM25 as (chunk, score) tuples
            k: Number of results to return
            
        Returns:
            Fused results sorted by RRF score
        """
        # Dictionary to accumulate scores
        # Key: chunk text (as unique identifier)
        # Value: {chunk, vector_score, bm25_score, total}
        scores = {}
        
        # Add vector search contribution
        for rank, chunk in enumerate(vector_results):
            chunk_key = chunk.text  # Use text as key
            vector_contribution = self.alpha / (self.RRF_K + rank)
            
            scores[chunk_key] = {
                'chunk': chunk,
                'vector_score': vector_contribution,
                'bm25_score': 0,
                'total': 0
            }
        
        # Add BM25 contribution
        for rank, (chunk, bm25_score) in enumerate(bm25_results):
            chunk_key = chunk.text
            bm25_contribution = (1 - self.alpha) / (self.RRF_K + rank)
            
            if chunk_key in scores:
                scores[chunk_key]['bm25_score'] = bm25_contribution
            else:
                scores[chunk_key] = {
                    'chunk': chunk,
                    'vector_score': 0,
                    'bm25_score': bm25_contribution,
                    'total': 0
                }
        
        # Calculate total RRF scores
        for chunk_key in scores:
            scores[chunk_key]['total'] = (
                scores[chunk_key]['vector_score'] + 
                scores[chunk_key]['bm25_score']
            )
        
        # Sort by total RRF score (descending)
        sorted_items = sorted(
            scores.values(),
            key=lambda x: x['total'],
            reverse=True
        )
        
        # Update chunks with RRF scores
        results = []
        for item in sorted_items[:k]:
            chunk = item['chunk']
            # Store RRF score as similarity_score
            chunk.similarity_score = item['total']
            # Store component scores in metadata
            chunk.metadata['rrf_vector_score'] = item['vector_score']
            chunk.metadata['rrf_bm25_score'] = item['bm25_score']
            results.append(chunk)
        
        return results
    
    def _filter_by_threshold(
        self, 
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Filter chunks by minimum similarity threshold.
        
        Removes low-quality results that could introduce noise
        or hallucination in generation.
        
        Args:
            chunks: Retrieved chunks
            
        Returns:
            Filtered chunks above threshold
        """
        filtered = [
            chunk for chunk in chunks
            if chunk.similarity_score >= self.min_similarity
        ]
        
        if not filtered:
            logger.warning(
                f"No results above threshold {self.min_similarity}",
                extra={"original_count": len(chunks)}
            )
        
        return filtered
    
    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "type": "hybrid",
            "alpha": self.alpha,
            "min_similarity": self.min_similarity,
            "rrf_k": self.RRF_K,
            "reranking_enabled": self.use_reranking,
            "bm25s_stats": self.bm25_index.get_stats()
        }
