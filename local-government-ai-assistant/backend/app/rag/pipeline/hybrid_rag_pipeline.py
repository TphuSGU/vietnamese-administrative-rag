"""
Enhanced RAG Pipeline with Hybrid Retrieval and Output Validation.

Architecture:
Query → [Input Validation] → [Hybrid Retrieval (BM25+Vector+Rerank)] 
     → [LLM Generation] → [Output Validation] → Response

Key improvements over basic RAGPipeline:
1. Hybrid retrieval: Combines keyword (BM25) + semantic (vector) search
2. Output validation: Prevents hallucination with evidence checking
3. Retry logic: If validation fails, retry with more chunks
4. Enhanced logging: Track validation results

Validates: Enhanced Requirements 8.1-8.6, 9.1-9.7
"""

import uuid
import time
import json
from pathlib import Path
from typing import Optional

from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.generation.llm_service import LLMService
from app.rag.generation.output_validator import OutputValidator
from app.models.data_models import RAGResponse, ChunkReference
from app.core.logging import get_logger
from app.models.exceptions import RAGValidationError

logger = get_logger(__name__)


class HybridRAGPipeline:
    """
    Enhanced RAG pipeline with hybrid retrieval and output validation.
    
    Process flow:
    1. Validate query (length, encoding)
    2. Hybrid retrieval (BM25 + Vector + Reranking)
    3. Generate answer with LLM
    4. Validate output (evidence, language, confidence)
    5. If validation fails, retry with more chunks (1 retry max)
    6. Return RAGResponse or error message
    
    Configuration:
    - alpha: Balance between vector (semantic) and BM25 (keyword) search
    - min_evidence_ratio: Minimum overlap between answer and context
    - max_retries: How many times to retry if validation fails
    """
    
    MIN_QUERY_LENGTH = 10
    MAX_QUERY_LENGTH = 500
    LOG_FILE = "hybrid_query_logs.jsonl"
    MAX_RETRIES = 1  # Max retries for failed validation
    
    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        llm_service: LLMService,
        output_validator: OutputValidator,
        log_dir: Optional[Path] = None
    ):
        """
        Initialize hybrid RAG pipeline.
        
        Args:
            hybrid_retriever: Hybrid retriever (BM25 + vector + reranking)
            llm_service: LLM service for answer generation
            output_validator: Validator to prevent hallucination
            log_dir: Directory for query logs
        """
        self.hybrid_retriever = hybrid_retriever
        self.llm_service = llm_service
        self.output_validator = output_validator
        
        # Setup logging directory
        self.log_dir = log_dir or Path("./logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / self.LOG_FILE
        
        logger.info(
            "HybridRAGPipeline initialized",
            extra={
                "retriever_type": "hybrid",
                "validator_enabled": True,
                "max_retries": self.MAX_RETRIES
            }
        )
    
    def _validate_query(self, query: str) -> None:
        """
        Validate query format and length.
        
        Args:
            query: User query
            
        Raises:
            RAGValidationError: If query is invalid
        """
        # Check empty
        if not query or not query.strip():
            raise RAGValidationError("Query cannot be empty")
        
        query = query.strip()
        
        # Check length bounds
        if len(query) < self.MIN_QUERY_LENGTH:
            raise RAGValidationError(
                f"Query too short (min {self.MIN_QUERY_LENGTH} chars)"
            )
        if len(query) > self.MAX_QUERY_LENGTH:
            raise RAGValidationError(
                f"Query too long (max {self.MAX_QUERY_LENGTH} chars)"
            )
        
        # Check UTF-8 encoding
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
        processing_time: float,
        validation_passed: bool,
        validation_error: Optional[str] = None,
        retry_count: int = 0
    ) -> None:
        """
        Log query with validation results.
        
        Args:
            query_id: Unique query identifier
            query: User query
            retrieved_chunks: Retrieved context chunks
            answer: Generated answer
            tokens_used: LLM tokens used
            processing_time: Total processing time
            validation_passed: Whether output validation passed
            validation_error: Validation error message if failed
            retry_count: Number of retries performed
        """
        log_entry = {
            "query_id": query_id,
            "timestamp": time.time(),
            "query": query,
            "num_chunks_retrieved": len(retrieved_chunks),
            "answer": answer,
            "tokens_used": tokens_used,
            "processing_time_ms": processing_time * 1000,
            "validation_passed": validation_passed,
            "validation_error": validation_error,
            "retry_count": retry_count
        }
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def query(
        self, 
        query: str, 
        k: int = 5
    ) -> RAGResponse:
        """
        Execute enhanced RAG pipeline with hybrid retrieval and validation.
        
        Args:
            query: User query in Vietnamese
            k: Number of chunks to retrieve initially
            
        Returns:
            RAGResponse with answer and metadata
            
        Process:
        1. Validate query
        2. Hybrid retrieval (BM25 + Vector + Rerank)
        3. Generate answer
        4. Validate output
        5. If validation fails, retry with more chunks (once)
        6. Return response or error message
        """
        start_time = time.time()
        query_id = str(uuid.uuid4())
        retry_count = 0
        
        logger.info(
            "Hybrid RAG query started",
            extra={
                "query_id": query_id,
                "query": query[:50],
                "k": k
            }
        )
        
        try:
            # Stage 1: Validate query
            self._validate_query(query)
            
            # Stage 2: Hybrid Retrieval
            try:
                retrieved_chunks = self.hybrid_retriever.retrieve(query, k=k)
            except Exception as e:
                logger.error(f"Hybrid retrieval failed: {e}")
                raise RAGValidationError(f"Retrieval stage failed: {e}")
            
            # Handle empty results
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
                    query_id, query, [], empty_response.answer, 0, 
                    processing_time, True
                )
                
                return empty_response
            
            # Stage 3: Generation + Validation Loop (with retry)
            generated_answer = None
            validation_passed = False
            validation_error = None
            
            current_k = k
            while retry_count <= self.MAX_RETRIES:
                # Generate answer
                try:
                    generated_answer = self.llm_service.generate_answer(
                        query, retrieved_chunks
                    )
                except Exception as e:
                    logger.error(f"Generation failed: {e}")
                    raise RAGValidationError(f"Generation stage failed: {e}")
                
                # Stage 4: Validate output
                logger.debug("Validating generated answer")
                validation_passed, validation_error = self.output_validator.validate(
                    answer=generated_answer.answer,
                    query=query,
                    context_chunks=retrieved_chunks
                )
                
                if validation_passed:
                    logger.info("Output validation passed")
                    break
                
                # Validation failed
                logger.warning(
                    f"Output validation failed: {validation_error}",
                    extra={"retry_count": retry_count}
                )
                
                # Retry with more chunks if retries remaining
                if retry_count < self.MAX_RETRIES:
                    retry_count += 1
                    current_k = min(current_k * 2, 20)  # Double k, max 20
                    
                    logger.info(
                        f"Retrying with more chunks: k={current_k}",
                        extra={"retry_count": retry_count}
                    )
                    
                    # Retrieve more chunks
                    try:
                        retrieved_chunks = self.hybrid_retriever.retrieve(
                            query, k=current_k
                        )
                    except Exception as e:
                        logger.error(f"Retry retrieval failed: {e}")
                        break
                else:
                    # Max retries reached
                    logger.warning("Max retries reached, returning with validation warning")
                    break
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # If validation never passed, return error response
            if not validation_passed:
                error_message = (
                    f"Xin lỗi, tôi không thể tạo câu trả lời đáng tin cậy từ "
                    f"tài liệu hiện có. Lý do: {validation_error}"
                )
                
                error_response = RAGResponse(
                    query_id=query_id,
                    answer=error_message,
                    source_chunks=[],
                    relevance_scores=[],
                    processing_time=processing_time,
                    model=self.llm_service.MODEL_NAME
                )
                
                self._log_query(
                    query_id, query, retrieved_chunks, error_message,
                    generated_answer.tokens_used if generated_answer else 0,
                    processing_time, False, validation_error, retry_count
                )
                
                return error_response
            
            # Build successful response
            relevance_scores = [
                chunk.similarity_score for chunk in retrieved_chunks
            ]
            
            response = RAGResponse(
                query_id=query_id,
                answer=generated_answer.answer,
                source_chunks=generated_answer.source_chunks,
                relevance_scores=relevance_scores,
                processing_time=processing_time,
                model=generated_answer.model
            )
            
            # Log successful query
            self._log_query(
                query_id,
                query,
                retrieved_chunks,
                generated_answer.answer,
                generated_answer.tokens_used,
                processing_time,
                validation_passed,
                None,
                retry_count
            )
            
            logger.info(
                "Hybrid RAG query completed",
                extra={
                    "query_id": query_id,
                    "processing_time_ms": processing_time * 1000,
                    "num_chunks": len(retrieved_chunks),
                    "validation_passed": validation_passed,
                    "retry_count": retry_count
                }
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Hybrid RAG query failed",
                extra={
                    "query_id": query_id,
                    "error": str(e),
                    "processing_time_ms": processing_time * 1000
                }
            )
            raise
    
    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        return {
            "pipeline_type": "hybrid",
            "retriever_stats": self.hybrid_retriever.get_stats(),
            "validator_enabled": True,
            "max_retries": self.MAX_RETRIES
        }
