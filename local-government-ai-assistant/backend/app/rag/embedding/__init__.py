"""
Embedding module for RAG system.

Provides EmbeddingService for converting Vietnamese text to dense vector embeddings
using bkai-foundation-models/vietnamese-bi-encoder model.
"""
from .embedding_service import EmbeddingService

__all__ = ["EmbeddingService"]
