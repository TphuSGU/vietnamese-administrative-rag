"""
Reranking layer using cross-encoder for improved precision.

Cross-Encoders vs Bi-Encoders:
- Bi-encoder: Encodes query and document separately, fast but less accurate
- Cross-encoder: Encodes query+document together, slow but very accurate

Use case:
- Initial retrieval: Bi-encoder (fast, get top 20-50 candidates)
- Reranking: Cross-encoder (accurate, reorder top 5-10 final results)

Solves: "Lost in the Middle" problem where LLMs ignore mid-context info.
"""

from typing import List
from sentence_transformers import CrossEncoder
import numpy as np

from app.models.data_models import RetrievedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


class Reranker:
    """
    Rerank retrieved chunks using cross-encoder.
    
    Model: ms-marco-MiniLM-L-6-v2
    - Trained on Microsoft MARCO dataset
    - 22M parameters (lightweight)
    - Fast inference (~10ms per pair)
    - Multilingual support (works with Vietnamese)
    
    Alternative models for Vietnamese:
    - 'cross-encoder/ms-marco-MiniLM-L-12-v2' (more accurate, slower)
    - Custom Vietnamese cross-encoder (if available)
    """
    
    MODEL_NAME = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
    
    def __init__(self, model_name: str = MODEL_NAME):
        """
        Initialize reranker with cross-encoder model.
        
        Args:
            model_name: Hugging Face model name
        """
        logger.info(f"Loading cross-encoder: {model_name}")
        
        try:
            self.cross_encoder = CrossEncoder(model_name)
            logger.info("Reranker initialized successfully")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")
            raise
    
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = 5
    ) -> List[RetrievedChunk]:
        """
        Rerank chunks using cross-encoder scores.
        
        Process:
        1. Create (query, chunk) pairs
        2. Score each pair with cross-encoder
        3. Sort by cross-encoder score
        4. Return top-K
        
        Args:
            query: User query
            chunks: Retrieved chunks to rerank
            top_k: Number of top results to return
            
        Returns:
            Reranked chunks with updated similarity scores
        """
        if not chunks:
            logger.warning("Rerank called with empty chunks list")
            return []
        
        logger.info(
            f"Reranking {len(chunks)} chunks",
            extra={"query": query[:50], "top_k": top_k}
        )
        
        # Create query-document pairs
        pairs = [(query, chunk.text) for chunk in chunks]
        
        # Get cross-encoder scores
        # Returns numpy array of scores
        scores = self.cross_encoder.predict(pairs)
        
        # Sort by cross-encoder score (descending)
        ranked_indices = np.argsort(scores)[::-1]
        
        # Build reranked results
        reranked_chunks = []
        for new_rank, original_idx in enumerate(ranked_indices[:top_k]):
            chunk = chunks[original_idx]
            
            # Update similarity score with cross-encoder score
            chunk.similarity_score = float(scores[original_idx])
            
            # Store ranking metadata
            chunk.metadata['original_rank'] = original_idx
            chunk.metadata['reranked_position'] = new_rank
            chunk.metadata['cross_encoder_score'] = float(scores[original_idx])
            
            reranked_chunks.append(chunk)
        
        logger.info(
            "Reranking completed",
            extra={
                "results_count": len(reranked_chunks),
                "top_score": reranked_chunks[0].similarity_score if reranked_chunks else 0,
                "score_range": (
                    float(np.min(scores)),
                    float(np.max(scores))
                )
            }
        )
        
        return reranked_chunks
    
    def batch_rerank(
        self,
        queries: List[str],
        chunks_list: List[List[RetrievedChunk]],
        top_k: int = 5
    ) -> List[List[RetrievedChunk]]:
        """
        Rerank multiple query-chunks pairs in batch.
        
        More efficient than reranking one by one.
        
        Args:
            queries: List of queries
            chunks_list: List of chunk lists (one per query)
            top_k: Number of results per query
            
        Returns:
            List of reranked chunk lists
        """
        results = []
        for query, chunks in zip(queries, chunks_list):
            reranked = self.rerank(query, chunks, top_k)
            results.append(reranked)
        return results
