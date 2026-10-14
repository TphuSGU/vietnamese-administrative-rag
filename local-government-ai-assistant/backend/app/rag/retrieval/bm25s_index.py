"""
BM25S keyword-based retrieval for hybrid search with persistence.

BM25S (Fast BM25) provides:
- 10-100x faster indexing and search compared to rank-bm25
- Persistent storage (save/load index from disk)
- Lower memory footprint
- Better for production with large document collections

Complements vector search (semantic) with keyword matching (lexical).
"""

from typing import List, Tuple, Dict, Optional
import bm25s
import numpy as np
import re
from pathlib import Path

from app.models.data_models import RetrievedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


class BM25SIndex:
    """
    BM25S keyword search index with persistence support.
    
    Algorithm: BM25 (Okapi BM25) with optimized implementation
    - Term frequency saturation
    - Document length normalization
    - Tunable parameters (k1, b)
    - Disk-based persistence for faster startup
    """
    
    def __init__(
        self, 
        k1: float = 1.5, 
        b: float = 0.75,
        persist_dir: Optional[Path] = None
    ):
        """
        Initialize BM25S index.
        
        Args:
            k1: Term frequency saturation parameter (default: 1.5)
                Higher = more emphasis on term frequency
            b: Length normalization parameter (default: 0.75)
                0 = no normalization, 1 = full normalization
            persist_dir: Directory to save/load index (None = no persistence)
        """
        self.k1 = k1
        self.b = b
        self.persist_dir = Path(persist_dir) if persist_dir else None
        self.retriever = None
        self.corpus_tokens = []
        self.chunk_map: Dict[int, RetrievedChunk] = {}
        self.word_pattern = re.compile(r'\b\w+\b', re.UNICODE)
        
        # Try to load existing index if persist_dir provided
        if self.persist_dir and self.persist_dir.exists():
            loaded = self.load_index(self.persist_dir)
            if loaded:
                logger.info(
                    "BM25SIndex loaded from disk",
                    extra={"persist_dir": str(self.persist_dir)}
                )
                return
        
        logger.info(
            "BM25SIndex initialized",
            extra={
                "k1": k1, 
                "b": b,
                "persist_dir": str(self.persist_dir) if self.persist_dir else None
            }
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
        Build BM25S index from chunks.
        
        Tokenization strategy:
        - Lowercase for case-insensitive matching
        - Split on whitespace
        - Preserve Vietnamese diacritics
        
        Args:
            chunks: List of chunks to index
        """
        if not chunks:
            logger.warning("Cannot build BM25S index: empty chunks list")
            return
        
        logger.info(f"Building BM25S index from {len(chunks)} chunks")
        
        # Tokenize corpus
        self.corpus_tokens = []
        self.chunk_map = {}
        
        for idx, chunk in enumerate(chunks):
            # Use improved tokenization (removes punctuation)
            tokens = self._tokenize(chunk.text)
            self.corpus_tokens.append(tokens)
            self.chunk_map[idx] = chunk
        
        # Build BM25S index with our custom tokens
        self.retriever = bm25s.BM25()
        self.retriever.index(self.corpus_tokens)
        
        # Save to disk if persistence enabled
        if self.persist_dir:
            self.save_index(self.persist_dir)
        
        avg_doc_length = np.mean([len(tokens) for tokens in self.corpus_tokens])
        
        logger.info(
            "BM25S index built successfully",
            extra={
                "corpus_size": len(self.corpus_tokens),
                "avg_doc_length": avg_doc_length,
                "persisted": self.persist_dir is not None
            }
        )
    
    def save_index(self, path: Path) -> bool:
        """
        Save index to disk for persistence.
        
        Args:
            path: Directory to save index files
            
        Returns:
            True if successful, False otherwise
        """
        if self.retriever is None:
            logger.warning("Cannot save: index not built")
            return False
        
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            # Save BM25S retriever
            self.retriever.save(str(path / "bm25s_index"))
            
            # Save corpus tokens as pickle (handles list of lists properly)
            import pickle
            with open(path / "corpus_tokens.pkl", 'wb') as f:
                pickle.dump(self.corpus_tokens, f)
            
            # Save chunk map metadata as pickle
            chunk_metadata = {
                idx: {
                    "text": chunk.text,
                    "similarity_score": chunk.similarity_score,
                    "metadata": chunk.metadata
                }
                for idx, chunk in self.chunk_map.items()
            }
            with open(path / "chunk_map.pkl", 'wb') as f:
                pickle.dump(chunk_metadata, f)
            
            logger.info(f"BM25S index saved to {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save BM25S index: {e}")
            return False
    
    def load_index(self, path: Path) -> bool:
        """
        Load index from disk.
        
        Args:
            path: Directory containing saved index files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            index_path = path / "bm25s_index"
            tokens_path = path / "corpus_tokens.pkl"
            chunk_map_path = path / "chunk_map.pkl"
            
            if not all(p.exists() for p in [tokens_path, chunk_map_path]):
                logger.warning(f"Index files not found in {path}")
                return False
            
            # Load BM25S retriever
            self.retriever = bm25s.BM25.load(str(index_path))
            
            # Load corpus tokens
            import pickle
            with open(tokens_path, 'rb') as f:
                self.corpus_tokens = pickle.load(f)
            
            # Load chunk map
            with open(chunk_map_path, 'rb') as f:
                chunk_metadata = pickle.load(f)
            
            self.chunk_map = {
                idx: RetrievedChunk(
                    text=data["text"],
                    similarity_score=data["similarity_score"],
                    metadata=data["metadata"]
                )
                for idx, data in chunk_metadata.items()
            }
            
            logger.info(
                f"BM25S index loaded from {path}",
                extra={"corpus_size": len(self.corpus_tokens)}
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to load BM25S index: {e}")
            return False
    
    def search(
        self, 
        query: str, 
        k: int = 10
    ) -> List[Tuple[RetrievedChunk, float]]:
        """
        Search using BM25S scoring.
        
        Args:
            query: Search query (Vietnamese text)
            k: Number of results to return
            
        Returns:
            List of (chunk, bm25_score) tuples, sorted by score descending
        """
        if self.retriever is None:
            logger.warning("BM25S index not built, returning empty results")
            return []
        
        # Tokenize query with improved tokenization
        query_tokens = self._tokenize(query)
        
        # BM25S expects list of token lists for batch queries
        query_tokens_batch = [query_tokens]
        
        # Get BM25S results
        # Returns (doc_ids, scores) for each query
        results, scores = self.retriever.retrieve(
            query_tokens_batch,
            k=min(k, len(self.corpus_tokens))
        )
        
        # Extract results for first query
        doc_indices = results[0]
        doc_scores = scores[0]
        
        # Build results with scores > 0
        output = []
        for idx, score in zip(doc_indices, doc_scores):
            if score > 0:  # Only include documents with positive scores
                chunk = self.chunk_map[int(idx)]
                output.append((chunk, float(score)))
        
        logger.info(
            "BM25S search completed",
            extra={
                "query": query[:50],
                "query_tokens": len(query_tokens),
                "results_count": len(output),
                "top_score": output[0][1] if output else 0
            }
        )
        
        return output
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        if self.retriever is None:
            return {"indexed": False}
        
        return {
            "indexed": True,
            "corpus_size": len(self.corpus_tokens),
            "avg_doc_length": np.mean([len(tokens) for tokens in self.corpus_tokens]),
            "k1": self.k1,
            "b": self.b,
            "persist_dir": str(self.persist_dir) if self.persist_dir else None
        }
