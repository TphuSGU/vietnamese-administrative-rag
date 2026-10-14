"""
BM25 keyword-based retrieval for hybrid search.

⚠️ DEPRECATED: This implementation uses rank-bm25 which is slower.
Use BM25SIndex (bm25s_index.py) instead for better performance and persistence.

BM25 (Best Matching 25) is effective for:
- Exact term matching (Điều 10, Khoản 3, CMND, CCCD)
- Named entities and technical terms
- Legal document references

Complements vector search (semantic) with keyword matching (lexical).
"""

from typing import List, Tuple, Dict
from rank_bm25 import BM25Okapi
import numpy as np
import re

from app.models.data_models import RetrievedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


class BM25Index:
    """
    BM25 keyword search index.
    
    Algorithm: BM25 (Okapi BM25)
    - Term frequency saturation
    - Document length normalization
    - Tunable parameters (k1, b)
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 index.
        
        Args:
            k1: Term frequency saturation parameter (default: 1.5)
                Higher = more emphasis on term frequency
            b: Length normalization parameter (default: 0.75)
                0 = no normalization, 1 = full normalization
        """
        self.k1 = k1
        self.b = b
        self.bm25 = None
        self.corpus_tokens = []
        self.chunk_map: Dict[int, RetrievedChunk] = {}
        self.word_pattern = re.compile(r'\b\w+\b', re.UNICODE)
        
        logger.info(
            "BM25Index initialized",
            extra={"k1": k1, "b": b}
        )
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing.
        
        Strategy:
        - Lowercase for case-insensitive matching
        - Extract words using Unicode word boundaries
        - Remove punctuation (handles Vietnamese punctuation properly)
        - Preserve Vietnamese diacritics
        
        Example:
            "Điều 10: Quyền" -> ["điều", "10", "quyền"]
            (not ["điều", "10:", "quyền"])
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens (lowercase words)
        """
        text_lower = text.lower()
        tokens = self.word_pattern.findall(text_lower)
        return [token for token in tokens if token]
    
    def index_chunks(self, chunks: List[RetrievedChunk]) -> None:
        """
        Build BM25 index from chunks.
        
        Tokenization strategy:
        - Lowercase for case-insensitive matching
        - Split on whitespace
        - Preserve Vietnamese diacritics
        
        Args:
            chunks: List of chunks to index
        """
        if not chunks:
            logger.warning("Cannot build BM25 index: empty chunks list")
            return
        
        logger.info(f"Building BM25 index from {len(chunks)} chunks")
        
        # Tokenize corpus
        self.corpus_tokens = []
        self.chunk_map = {}
        
        for idx, chunk in enumerate(chunks):
            # Use improved tokenization (removes punctuation)
            tokens = self._tokenize(chunk.text)
            self.corpus_tokens.append(tokens)
            self.chunk_map[idx] = chunk
        
        # Build BM25 index
        self.bm25 = BM25Okapi(
            self.corpus_tokens,
            k1=self.k1,
            b=self.b
        )
        
        avg_doc_length = np.mean([len(tokens) for tokens in self.corpus_tokens])
        
        logger.info(
            "BM25 index built successfully",
            extra={
                "corpus_size": len(self.corpus_tokens),
                "avg_doc_length": avg_doc_length
            }
        )
    
    def search(
        self, 
        query: str, 
        k: int = 10
    ) -> List[Tuple[RetrievedChunk, float]]:
        """
        Search using BM25 scoring.
        
        Args:
            query: Search query (Vietnamese text)
            k: Number of results to return
            
        Returns:
            List of (chunk, bm25_score) tuples, sorted by score descending
        """
        if self.bm25 is None:
            logger.warning("BM25 index not built, returning empty results")
            return []
        
        # Tokenize query with improved tokenization
        query_tokens = self._tokenize(query)
        
        # Get BM25 scores for all documents
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top K indices
        top_indices = np.argsort(scores)[::-1][:k]
        
        # Build results with scores > 0
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0:  # Only include documents with positive scores
                chunk = self.chunk_map[idx]
                results.append((chunk, score))
        
        logger.info(
            "BM25 search completed",
            extra={
                "query": query[:50],
                "query_tokens": len(query_tokens),
                "results_count": len(results),
                "top_score": results[0][1] if results else 0
            }
        )
        
        return results
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        if self.bm25 is None:
            return {"indexed": False}
        
        return {
            "indexed": True,
            "corpus_size": len(self.corpus_tokens),
            "avg_doc_length": np.mean([len(tokens) for tokens in self.corpus_tokens]),
            "k1": self.k1,
            "b": self.b
        }
