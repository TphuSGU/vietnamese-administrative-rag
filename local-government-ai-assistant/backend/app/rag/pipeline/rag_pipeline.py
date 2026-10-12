"""
Complete RAG Pipeline orchestration.
Validates: Requirements 7.1, 7.2, 7.3, 10.1, 10.2, 10.3, 10.4, 10.5, 16.3
"""

import uuid
import time
import json
from pathlib import Path
from typing import Optional

from app.rag.retrieval.retriever import Retriever
from app.rag.generation.llm_service import LLMService
from app.models.data_models import RAGResponse, ChunkReference
from app.core.logging import get_logger
from app.models.exceptions import RAGValidationError

logger = get_logger(__name__)


class RAGPipeline:
    """
    Complete RAG pipeline: Query → Retrieval → Generation.
    
    Validates: Requirements 7.1, 7.2, 7.3, 10.1, 10.2, 10.3, 10.4, 10.5
    """
    
    MIN_QUERY_LENGTH = 10
    MAX_QUERY_LENGTH = 500
    LOG_FILE = "query_logs.jsonl"
    
    def __init__(
        self,
        retriever: Retriever,
        llm_service: LLMService,
        log_dir: Optional[Path] = None
    ):
        self.retriever = retriever
        self.llm_service = llm_service
        
        # Setup logging directory (Req 16.3)
        self.log_dir = log_dir or Path("./logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / self.LOG_FILE
        
        logger.info("RAGPipeline initialized")
    
    def _validate_query(self, query: str) -> None:
        """
        Validate query format and length.
        
        Args:
            query: User query
            
        Raises:
            RAGValidationError: If query is invalid
            
        Validates: Requirements 10.1, 10.2
        """
        # Check empty
        if not query or not query.strip():
            raise RAGValidationError("Query cannot be empty")
        
        query = query.strip()
        
        # Check length bounds (Req 10.1)
        if len(query) < self.MIN_QUERY_LENGTH:
            raise RAGValidationError(
                f"Query too short (min {self.MIN_QUERY_LENGTH} chars)"
            )
        if len(query) > self.MAX_QUERY_LENGTH:
            raise RAGValidationError(
                f"Query too long (max {self.MAX_QUERY_LENGTH} chars)"
            )
        
        # Check UTF-8 encoding (Req 10.2)
        try:
            query.encode('utf-8')
        except UnicodeEncodeError:
            raise RAGValidationError("Query must be valid UTF-8")
    
    def _log_query(
        self,
        query_id: str,
        query: str,
        retrieved_chunks: list,
        answer: str,
        tokens_used: Optional[int],
        processing_time: float
    ) -> None:
        """
        Log query to JSONL file.
        
        Validates: Requirement 16.3
        """
        log_entry = {
            "query_id": query_id,
            "timestamp": time.time(),
            "query": query,
            "num_chunks_retrieved": len(retrieved_chunks),
            "answer": answer,
            "tokens_used": tokens_used,
            "processing_time_ms": processing_time * 1000
        }
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def query(
        self, 
        query: str, 
        k: int = 5
    ) -> RAGResponse:
        """
        Execute complete RAG pipeline.
        
        Args:
            query: User query in Vietnamese
            k: Number of chunks to retrieve
            
        Returns:
            RAGResponse with answer and metadata
            
        Validates: Requirements 7.1, 7.2, 7.3, 10.3, 10.4, 10.5
        """
        start_time = time.time()
        query_id = str(uuid.uuid4())
        
        logger.info(
            "RAG query started",
            extra={"query_id": query_id, "query": query[:50], "k": k}
        )
        
        try:
            # Stage 1: Validate query (Req 10.1, 10.2)
            self._validate_query(query)
            
            # Stage 2: Retrieval (Req 7.1)
            try:
                retrieved_chunks = self.retriever.retrieve(query, k=k)
            except Exception as e:
                logger.error(f"Retrieval failed: {e}")
                raise RAGValidationError(f"Retrieval stage failed: {e}")
            
            # Handle empty results (Req 10.4)
            if not retrieved_chunks:
                processing_time = time.time() - start_time
                empty_response = RAGResponse(
                    query_id=query_id,
                    answer="Không tìm thấy tài liệu liên quan đến câu hỏi của bạn.",
                    source_chunks=[],
                    relevance_scores=[],
                    processing_time=processing_time,
                    model=self.llm_service.MODEL_NAME
                )
                
                self._log_query(
                    query_id, query, [], empty_response.answer, 0, processing_time
                )
                
                return empty_response
            
            # Stage 3: Generation (Req 7.2)
            try:
                generated_answer = self.llm_service.generate_answer(
                    query, retrieved_chunks
                )
            except Exception as e:
                logger.error(f"Generation failed: {e}")
                raise RAGValidationError(f"Generation stage failed: {e}")
            
            # Calculate processing time (Req 10.5)
            processing_time = time.time() - start_time
            
            # Extract relevance scores
            relevance_scores = [chunk.similarity_score for chunk in retrieved_chunks]
            
            # Build response (Req 7.3)
            response = RAGResponse(
                query_id=query_id,
                answer=generated_answer.answer,
                source_chunks=generated_answer.source_chunks,
                relevance_scores=relevance_scores,
                processing_time=processing_time,
                model=generated_answer.model
            )
            
            # Log query (Req 16.3)
            self._log_query(
                query_id,
                query,
                retrieved_chunks,
                generated_answer.answer,
                generated_answer.tokens_used,
                processing_time
            )
            
            logger.info(
                "RAG query completed",
                extra={
                    "query_id": query_id,
                    "processing_time_ms": processing_time * 1000,
                    "num_chunks": len(retrieved_chunks)
                }
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "RAG query failed",
                extra={
                    "query_id": query_id,
                    "error": str(e),
                    "processing_time_ms": processing_time * 1000
                }
            )
            raise
