"""
EmbeddingService using vietnamese-bi-encoder model.

Implements Requirements 4.1-4.6 from design document:
- Model: bkai-foundation-models/vietnamese-bi-encoder
- Output: 768-dimensional vectors
- Batch processing: 32 chunks per batch
- L2 normalization for cosine similarity
- Error handling for individual chunks
- Performance logging

Uses sentence-transformers library which automatically handles:
- Tokenization
- Forward pass
- Mean pooling
- L2 normalization
"""
import time
from typing import List, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.logging import get_logger
from app.models.data_models import Chunk

logger = get_logger("embedding_service")


class EmbeddingService:
    """
    Generates embeddings using vietnamese-bi-encoder model.
    
    Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
    """
    
    MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"
    EMBEDDING_DIM = 768
    DEFAULT_BATCH_SIZE = 32
    
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        batch_size: int = DEFAULT_BATCH_SIZE,
        device: Optional[str] = None
    ):
        """
        Initialize embedding service with vietnamese-bi-encoder.
        
        Args:
            model_name: Model identifier or local path
            batch_size: Number of texts to process per batch
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
        """
        logger.info(
            "Initializing EmbeddingService",
            extra={
                "model": model_name,
                "batch_size": batch_size,
                "device": device or "auto"
            }
        )
        
        start_time = time.time()
        
        try:
            # Load model using sentence-transformers
            # It automatically handles tokenization, pooling, and normalization
            self.model = SentenceTransformer(model_name, device=device)
            self.batch_size = batch_size
            self.device = device or self.model.device
            
            load_time = time.time() - start_time
            
            logger.info(
                "EmbeddingService initialized successfully",
                extra={
                    "model": model_name,
                    "device": str(self.device),
                    "load_time_seconds": round(load_time, 2),
                    "embedding_dim": self.EMBEDDING_DIM
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to load embedding model",
                extra={
                    "model": model_name,
                    "error": str(e)
                }
            )
            raise RuntimeError(f"Failed to load embedding model: {e}")
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Validates: Requirements 4.2, 4.3, 4.5
        
        Args:
            texts: List of text strings (from Chunk objects)
            
        Returns:
            numpy array of shape (len(texts), 768)
            Each row is a normalized 768-dim vector
            
        Raises:
            ValueError: If texts list is empty
        """
        if not texts:
            raise ValueError("Cannot embed empty list of texts")
        
        start_time = time.time()
        
        try:
            # sentence-transformers handles batch processing automatically
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True  # L2 normalization (Req 4.5)
            )
            
            duration = time.time() - start_time
            
            # Validate embeddings
            self._validate_embeddings(embeddings)
            
            logger.info(
                "Embeddings generated successfully",
                extra={
                    "num_texts": len(texts),
                    "embedding_shape": embeddings.shape,
                    "duration_seconds": round(duration, 2),
                    "texts_per_second": round(len(texts) / duration, 2) if duration > 0 else 0
                }
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(
                "Embedding generation failed",
                extra={
                    "num_texts": len(texts),
                    "error": str(e)
                }
            )
            raise RuntimeError(f"Failed to generate embeddings: {e}")
    
    def embed_chunks(self, chunks: List[Chunk]) -> np.ndarray:
        """
        Generate embeddings for Chunk objects.
        
        Validates: Requirements 4.2, 4.3
        
        Args:
            chunks: List of Chunk objects
            
        Returns:
            numpy array of shape (len(chunks), 768)
        """
        if not chunks:
            raise ValueError("Cannot embed empty list of chunks")
        
        texts = [chunk.text for chunk in chunks]
        return self.embed_texts(texts)
    
    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text (for queries).
        
        Validates: Requirements 4.2, 4.5
        
        Args:
            text: Single text string
            
        Returns:
            numpy array of shape (768,) - single normalized vector
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")
        
        embeddings = self.embed_texts([text])
        return embeddings[0]
    
    def embed_texts_with_fallback(
        self, 
        texts: List[str]
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Generate embeddings with error handling for individual chunks.
        
        Validates: Requirements 4.4
        
        Returns:
            Tuple of (embeddings, failed_indices)
            - embeddings: Valid embeddings (may have fewer rows than input)
            - failed_indices: List of indices that failed
        """
        valid_embeddings = []
        failed_indices = []
        
        for i, text in enumerate(texts):
            try:
                embedding = self.model.encode(
                    [text],
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
                valid_embeddings.append(embedding[0])
            except Exception as e:
                logger.error(
                    f"Failed to embed chunk at index {i}",
                    extra={
                        "chunk_index": i,
                        "text_length": len(text),
                        "error": str(e)
                    }
                )
                failed_indices.append(i)
        
        if not valid_embeddings:
            raise RuntimeError("All embedding attempts failed")
        
        embeddings_array = np.array(valid_embeddings)
        
        logger.warning(
            "Embedding with fallback completed",
            extra={
                "total_texts": len(texts),
                "successful": len(valid_embeddings),
                "failed": len(failed_indices),
                "failed_indices": failed_indices
            }
        )
        
        return embeddings_array, failed_indices
    
    def _validate_embeddings(self, embeddings: np.ndarray) -> None:
        """
        Validate embedding properties.
        
        Validates: Requirements 4.2, 4.5
        
        Checks:
        - Shape is (N, 768)
        - All vectors are normalized (L2 norm ≈ 1.0)
        - No NaN or Inf values
        
        Raises:
            AssertionError: If validation fails
        """
        # Check dimensions
        if len(embeddings.shape) != 2:
            raise AssertionError(
                f"Expected 2D array, got shape {embeddings.shape}"
            )
        
        if embeddings.shape[1] != self.EMBEDDING_DIM:
            raise AssertionError(
                f"Expected {self.EMBEDDING_DIM} dimensions, "
                f"got {embeddings.shape[1]}"
            )
        
        # Check for invalid values
        if np.isnan(embeddings).any():
            raise AssertionError("Embeddings contain NaN values")
        
        if np.isinf(embeddings).any():
            raise AssertionError("Embeddings contain Inf values")
        
        # Check normalization (L2 norm should be ≈ 1.0)
        norms = np.linalg.norm(embeddings, axis=1)
        if not np.allclose(norms, 1.0, atol=0.01):
            max_deviation = np.max(np.abs(norms - 1.0))
            raise AssertionError(
                f"Vectors not properly normalized. "
                f"Max deviation from 1.0: {max_deviation:.4f}"
            )
    
    def get_embedding_dim(self) -> int:
        """
        Return embedding dimensions.
        
        Returns:
            768 for vietnamese-bi-encoder
        """
        return self.EMBEDDING_DIM
    
    def health_check(self) -> bool:
        """
        Check if model is loaded and functional.
        
        Returns:
            True if model can generate embeddings, False otherwise
        """
        try:
            # Try embedding a simple test text
            test_text = "Test tiếng Việt"
            embedding = self.embed_single(test_text)
            
            # Verify output shape
            if embedding.shape != (self.EMBEDDING_DIM,):
                logger.error(
                    "Health check failed: unexpected embedding shape",
                    extra={"shape": embedding.shape}
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(
                "Health check failed",
                extra={"error": str(e)}
            )
            return False
