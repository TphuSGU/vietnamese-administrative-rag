"""
ChromaDB Vector Store implementation for document embeddings.

Implements Requirement 5: Vector Storage with cosine similarity search,
incremental indexing, and document deletion support.

Features:
- 768-dimensional embeddings from vietnamese-bi-encoder
- Cosine similarity search with HNSW indexing
- Persistent storage with ChromaDB
- Document chunk metadata tracking
- <500ms search latency for 10K documents
"""

import time
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings
import numpy as np

from app.models.data_models import Chunk, SearchResult
from app.models.exceptions import VectorStoreError
from app.core.logging import get_logger

logger = get_logger(__name__)


class VectorStore:
    """
    Vector storage using ChromaDB with cosine similarity.
    
    Stores 768-dimensional embeddings from vietnamese-bi-encoder
    with document chunk metadata.
    
    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
    """
    
    COLLECTION_NAME = "vietnamese_documents"
    EMBEDDING_DIM = 768
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize ChromaDB vector store.
        
        Args:
            persist_directory: Directory for persistent storage
            
        Raises:
            VectorStoreError: If initialization fails
        """
        try:
            # Create persistent client
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection with cosine similarity
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",           # Cosine similarity
                    "hnsw:construction_ef": 200,       # Construction quality
                    "hnsw:search_ef": 100,             # Search quality
                    "hnsw:M": 16                       # Max connections per element
                }
            )
            
            logger.info(
                "VectorStore initialized",
                extra={
                    "collection": self.COLLECTION_NAME,
                    "persist_directory": persist_directory,
                    "embedding_dim": self.EMBEDDING_DIM
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize VectorStore: {e}")
            raise VectorStoreError(f"VectorStore initialization failed: {e}")
    
    def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: np.ndarray
    ) -> None:
        """
        Store chunk embeddings with metadata.
        
        Args:
            chunks: List of Chunk objects (from SemanticChunker)
            embeddings: Array of shape (len(chunks), 768)
            
        Raises:
            VectorStoreError: If storage fails
            ValueError: If inputs are invalid
            
        Validates: Requirements 5.1, 5.5
        """
        # Validate inputs
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Number of chunks ({len(chunks)}) and embeddings "
                f"({len(embeddings)}) must match"
            )
        
        if len(embeddings) == 0:
            logger.warning("No chunks to add")
            return
        
        if embeddings.shape[1] != self.EMBEDDING_DIM:
            raise ValueError(
                f"Expected {self.EMBEDDING_DIM}-dim embeddings, "
                f"got {embeddings.shape[1]}"
            )
        
        try:
            # Prepare data for ChromaDB
            ids = [
                f"{chunk.document_id}_{chunk.chunk_index}"
                for chunk in chunks
            ]
            
            metadatas = [
                {
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "heading_context": chunk.heading_context or "",
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "timestamp": datetime.utcnow().isoformat()
                }
                for chunk in chunks
            ]
            
            documents = [chunk.text for chunk in chunks]
            
            # Convert embeddings to list format for ChromaDB
            embeddings_list = embeddings.tolist()
            
            # Add to collection (incremental indexing - Req 5.5)
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                metadatas=metadatas,
                documents=documents
            )
            
            logger.info(
                f"Added {len(chunks)} chunks to vector store",
                extra={
                    "chunk_count": len(chunks),
                    "document_id": chunks[0].document_id if chunks else None
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to add chunks to vector store: {e}")
            raise VectorStoreError(f"Failed to add chunks: {e}")
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5
    ) -> List[SearchResult]:
        """
        Search for similar chunks using cosine similarity.
        
        Args:
            query_embedding: Query vector of shape (768,)
            k: Number of results to return (default: 5)
            
        Returns:
            List of SearchResult objects sorted by similarity (descending)
            
        Raises:
            VectorStoreError: If search fails
            ValueError: If query embedding is invalid
            
        Validates: Requirements 5.2, 5.3 - <500ms for 10K documents
        """
        start_time = time.time()
        
        # Validate query embedding
        if query_embedding.ndim == 1:
            expected_shape = (self.EMBEDDING_DIM,)
        else:
            expected_shape = (1, self.EMBEDDING_DIM)
        
        if query_embedding.shape != expected_shape:
            raise ValueError(
                f"Expected {expected_shape} query embedding, "
                f"got {query_embedding.shape}"
            )
        
        try:
            # Convert to list for ChromaDB
            if query_embedding.ndim == 1:
                query_list = query_embedding.tolist()
            else:
                query_list = query_embedding[0].tolist()
            
            # Perform similarity search
            results = self.collection.query(
                query_embeddings=[query_list],
                n_results=k,
                include=["documents", "metadatas", "distances"]
            )
            
            search_time = time.time() - start_time
            
            # Convert to SearchResult objects
            search_results = []
            
            if results["ids"] and len(results["ids"][0]) > 0:
                for i in range(len(results["ids"][0])):
                    # ChromaDB returns distance, convert to similarity score
                    # For cosine distance: similarity = 1 - distance
                    distance = results["distances"][0][i]
                    similarity = 1.0 - distance
                    
                    search_result = SearchResult(
                        chunk_id=results["ids"][0][i],
                        text=results["documents"][0][i],
                        metadata=results["metadatas"][0][i],
                        similarity_score=similarity,
                        distance=distance
                    )
                    search_results.append(search_result)
            
            # Log performance
            logger.info(
                "Search completed",
                extra={
                    "k": k,
                    "results_found": len(search_results),
                    "search_time_ms": round(search_time * 1000, 2)
                }
            )
            
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise VectorStoreError(f"Search failed: {e}")
    
    def delete_document(self, document_id: str) -> int:
        """
        Delete all chunks for a document.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            Number of chunks deleted
            
        Raises:
            VectorStoreError: If deletion fails
            
        Validates: Requirements 5.6
        """
        try:
            # Query all chunks for this document
            results = self.collection.get(
                where={"document_id": document_id},
                include=["metadatas"]
            )
            
            chunk_ids = results["ids"]
            
            if not chunk_ids:
                logger.warning(f"No chunks found for document_id: {document_id}")
                return 0
            
            # Delete chunks
            self.collection.delete(ids=chunk_ids)
            
            logger.info(
                f"Deleted {len(chunk_ids)} chunks for document {document_id}",
                extra={
                    "document_id": document_id,
                    "chunks_deleted": len(chunk_ids)
                }
            )
            
            return len(chunk_ids)
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise VectorStoreError(f"Failed to delete document: {e}")
    
    def health_check(self) -> bool:
        """
        Verify ChromaDB connection and collection status.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check collection exists
            collections = self.client.list_collections()
            collection_names = [c.name for c in collections]
            
            if self.COLLECTION_NAME not in collection_names:
                logger.error("Collection not found")
                return False
            
            # Check collection metadata
            count = self.collection.count()
            
            logger.info(
                "VectorStore health check passed",
                extra={
                    "collection": self.COLLECTION_NAME,
                    "chunk_count": count
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dictionary with collection name, count, and embedding dimension
        """
        try:
            return {
                "name": self.COLLECTION_NAME,
                "count": self.collection.count(),
                "embedding_dim": self.EMBEDDING_DIM
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "name": self.COLLECTION_NAME,
                "count": 0,
                "embedding_dim": self.EMBEDDING_DIM,
                "error": str(e)
            }
    
    def clear_collection(self) -> None:
        """
        Clear all data from collection (use with caution).
        
        Raises:
            VectorStoreError: If clearing fails
        """
        try:
            # Delete and recreate collection
            self.client.delete_collection(self.COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:search_ef": 100,
                    "hnsw:M": 16
                }
            )
            
            logger.warning("Collection cleared - all data deleted")
            
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise VectorStoreError(f"Failed to clear collection: {e}")
