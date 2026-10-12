# Implementation Plan: RAG LLM Core System

## Overview

This plan outlines the implementation of a Retrieval-Augmented Generation (RAG) system optimized for Vietnamese government documents. The system uses VietAI embeddings for semantic search, ChromaDB for vector storage, and OpenAI GPT models for answer generation. Implementation will be in Python using FastAPI.

The implementation follows a bottom-up approach: building foundational components (data models, utilities), then core pipeline components (loader, cleaner, chunker, embeddings), followed by storage and retrieval, then orchestration, and finally the API layer and evaluation framework.

## Tasks

- [ ] 1. Project setup and core infrastructure
  - [ ] 1.1 Set up project structure and configuration management
    - Create directory structure following the design: `app/core/`, `app/rag/{ingestion,embedding,retrieval,generation,pipeline,evaluation}/`, `app/api/`, `app/database/`, `app/models/`
    - Implement `Settings` class using Pydantic BaseSettings for configuration from environment variables
    - Create `.env.example` file with all required configuration parameters
    - Implement configuration validation function that checks OpenAI API key, chunk size constraints, and K value constraints
    - Set up structured logging with JSON formatter and sensitive data redaction
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 15.1, 15.2, 15.6_

  - [ ] 1.2 Define core data models and exceptions
    - Implement dataclasses for `Document`, `Chunk`, `SearchResult`, `RetrievedChunk`, `ChunkReference`, `GeneratedAnswer`, `RAGResponse`, `IngestionResult`, `EvaluationDataset`, `EvaluationReport`
    - Define exception hierarchy: `RAGException` (base), `DocumentLoadError`, `EmbeddingError`, `VectorStoreError`, `RAGValidationError`, `RAGPipelineError`, `LLMGenerationError`
    - Create `IngestionStatus` enum with values: {pending, processing, completed, failed}
    - _Requirements: 1.4, 3.6, 5.1, 6.5, 8.4, 9.7, 10.5, 11.6, 12.5, 16.5_

  - [ ] 1.3 Set up testing framework
    - Configure pytest with asyncio support
    - Configure Hypothesis for property-based testing with minimum 100 iterations
    - Create test fixtures for mock documents, chunks, and embeddings
    - Set up test data directory with sample Vietnamese documents (PDF, DOCX, TXT)
    - _Requirements: All (testing support)_

- [ ] 2. Document ingestion pipeline components
  - [ ] 2.1 Implement Document Loader
    - Implement `DocumentLoader` class with support for PDF (using PyPDF2 or pdfplumber), DOCX (python-docx), and TXT formats
    - Implement UTF-8 encoding enforcement for all extracted text
    - Implement metadata extraction: filename, upload timestamp, file size, format
    - Implement error handling with `DocumentLoadError` for unsupported formats and extraction failures
    - Add logging for document load operations with performance metrics
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 15.4_

  - [ ]* 2.2 Write property test for Document Loader
    - **Property 1: UTF-8 Encoding Preservation**
    - **Property 2: Document Metadata Completeness**
    - **Validates: Requirements 1.2, 1.4**

  - [ ] 2.3 Implement Text Cleaner
    - Implement `TextCleaner` class with `clean()` method
    - Implement Unicode normalization to NFC form using `unicodedata.normalize()`
    - Implement control character removal (except `\n` and `\t`)
    - Implement whitespace normalization (single spaces, preserve paragraph breaks with `\n\n`)
    - Verify Vietnamese diacritics preservation post-normalization
    - Implement lowercase conversion
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 2.4 Write property tests for Text Cleaner
    - **Property 3: Unicode Normalization Idempotence**
    - **Property 4: Whitespace Cleaning Invariant**
    - **Property 5: Diacritics Preservation**
    - **Property 6: Control Character Filtering**
    - **Property 7: Lowercase Conversion Completeness**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

  - [ ] 2.5 Implement Semantic Chunker
    - Implement `SemanticChunker` class with configurable `MIN_CHUNK_SIZE` (200) and `MAX_CHUNK_SIZE` (1000)
    - Implement heading detection using patterns: lines ending with `:`, ALL CAPS lines, "Điều X"/"Chương X"/"Phần X" patterns, short lines followed by paragraphs
    - Implement paragraph-based splitting at `\n\n` boundaries
    - Implement size enforcement logic: merge small paragraphs (<200 chars), keep medium (200-1000), split large at sentence boundaries, split very large sentences at clause boundaries
    - Implement Vietnamese sentence detection using regex: `r'[.!?;]\s+(?=[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])'`
    - Implement chunk metadata attachment: document_id, chunk_index, heading_context, char_start, char_end
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 2.6 Write property tests for Semantic Chunker
    - **Property 8: Chunk Size Bounds**
    - **Property 9: Chunk Metadata Completeness**
    - **Validates: Requirements 3.5, 3.6**

  - [ ]* 2.7 Write unit tests for Semantic Chunker
    - Test heading detection with various Vietnamese patterns
    - Test paragraph merging for small chunks
    - Test sentence splitting for oversized paragraphs
    - Test clause splitting for oversized sentences
    - Test edge cases: empty text, single sentence, no headings
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 3. Embedding service implementation
  - [ ] 3.1 Implement VietAI Embedding Service
    - Implement `EmbeddingService` class with VietAI/vit5-base-vietnamese-embedding model
    - Implement model loading using `transformers.AutoModel.from_pretrained()` with local path or download
    - Implement tokenizer loading using `transformers.AutoTokenizer.from_pretrained()`
    - Implement embedding generation with mean pooling: tokenize → forward pass → mean pooling over attention mask → L2 normalization
    - Implement batch processing with `BATCH_SIZE=32`
    - Implement error handling for individual chunk failures (log and continue)
    - Add performance logging for embedding generation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 15.4_

  - [ ]* 3.2 Write property tests for Embedding Service
    - **Property 10: Embedding Dimensionality**
    - **Property 11: Embedding Batch Consistency**
    - **Property 12: Embedding Normalization**
    - **Validates: Requirements 4.2, 4.3, 4.5**

  - [ ]* 3.3 Write unit tests for Embedding Service
    - Test model loading from local path
    - Test model downloading from Hugging Face
    - Test embedding generation for sample Vietnamese texts
    - Test batch processing splits large lists correctly
    - Test error handling for invalid inputs
    - _Requirements: 4.1, 4.4_

- [ ] 4. Vector store implementation
  - [ ] 4.1 Implement ChromaDB Vector Store
    - Implement `VectorStore` class with ChromaDB PersistentClient
    - Configure ChromaDB collection with cosine similarity: `{"hnsw:space": "cosine", "hnsw:construction_ef": 200, "hnsw:search_ef": 100, "hnsw:M": 16}`
    - Implement `add_chunks()` method to store embeddings with metadata (document_id, chunk_index, heading_context, char_start, char_end, timestamp)
    - Implement `search()` method for similarity search returning top K results sorted by score
    - Implement `delete_document()` method to remove all chunks for a document ID
    - Implement `health_check()` method to verify connection
    - Add error handling with `VectorStoreError`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 4.2 Write property tests for Vector Store
    - **Property 13: Vector Store Round-Trip**
    - **Property 14: Similarity Score Ordering**
    - **Property 15: Document Deletion Completeness**
    - **Validates: Requirements 5.1, 5.2, 5.6_

  - [ ]* 4.3 Write unit tests for Vector Store
    - Test collection creation and configuration
    - Test incremental indexing (add chunks without rebuilding)
    - Test search performance with 10,000 documents (< 500ms for K=5)
    - Test empty collection handling
    - Test concurrent access scenarios
    - _Requirements: 5.3, 5.4, 5.5_

- [ ] 5. Document ingestion pipeline orchestration
  - [ ] 5.1 Implement Ingestion Pipeline with status tracking
    - Implement `IngestionStatusTracker` with thread-safe status management using asyncio.Lock
    - Implement `DocumentIngestionPipeline` class that orchestrates loader → cleaner → chunker → embedding → storage
    - Implement `ingest_document()` method with job ID generation and status tracking
    - Implement error handling at each stage with descriptive logging (stage identification, document details)
    - Implement concurrency control with asyncio.Semaphore(4) for up to 4 parallel pipelines
    - Implement `get_status()` and `get_result()` methods for job tracking
    - Return `IngestionResult` with job_id, status, chunk_count, document_id
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 15.1, 15.4_

  - [ ]* 5.2 Write property test for Ingestion Pipeline
    - **Property 16: Ingestion Status Validity**
    - **Validates: Requirements 6.5**

  - [ ]* 5.3 Write integration tests for Ingestion Pipeline
    - Test end-to-end ingestion of PDF, DOCX, TXT documents
    - Test error recovery at each pipeline stage
    - Test concurrent ingestion of multiple documents
    - Test status tracking throughout pipeline execution
    - Verify chunks are stored in vector store after successful ingestion
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 6. Checkpoint - Verify ingestion pipeline
  - Ensure all tests pass for ingestion components (loader, cleaner, chunker, embedding, vector store, pipeline)
  - Manually test ingestion with sample Vietnamese documents
  - Verify chunks are correctly stored in ChromaDB
  - Ask the user if questions arise

- [ ] 7. Retrieval and generation components
  - [ ] 7.1 Implement Retriever
    - Implement `Retriever` class with `DEFAULT_K=5`, `MIN_K=1`, `MAX_K=20`
    - Implement K parameter validation in `retrieve()` method
    - Implement query embedding using `EmbeddingService`
    - Implement vector store search with K parameter
    - Return list of `RetrievedChunk` objects sorted by similarity (descending)
    - Include similarity scores with each chunk
    - _Requirements: 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 7.2 Write property tests for Retriever
    - **Property 18: Retrieval K Bounds**
    - **Property 19: Retrieval Result Count**
    - **Property 20: Similarity Score Presence**
    - **Validates: Requirements 8.1, 8.3, 8.5**

  - [ ] 7.3 Implement LLM Service for answer generation
    - Implement `LLMService` class with OpenAI AsyncOpenAI client
    - Implement prompt construction with Vietnamese instructions and context formatting
    - Format retrieved chunks as "[Tài liệu {i}] ({heading}):\n{text}"
    - Include system message: "Bạn là trợ lý AI hỗ trợ công dân tra cứu thông tin về văn bản chính quyền địa phương"
    - Include instructions for: answer based on provided documents, respond in Vietnamese, cite sources, state if insufficient information
    - Implement answer generation with `MAX_TOKENS=500`, `temperature=0.3`
    - Implement retry logic using tenacity (3 retries with exponential backoff) for OpenAI API errors
    - Return `GeneratedAnswer` with answer text, source chunks, model name, tokens used
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 15.3_

  - [ ]* 7.4 Write property tests for LLM Service
    - **Property 21: Prompt Completeness**
    - **Property 22: Vietnamese Response Instruction**
    - **Property 23: Answer Token Limit**
    - **Property 24: Answer Completeness**
    - **Validates: Requirements 9.2, 9.3, 9.4, 9.6, 9.7**

  - [ ]* 7.5 Write unit tests for LLM Service
    - Test prompt construction with various chunk combinations
    - Test heading context inclusion in prompts
    - Test "insufficient information" handling
    - Test retry logic for API failures
    - Test token counting and limit enforcement
    - _Requirements: 9.1, 9.5, 15.3_

- [ ] 8. RAG pipeline orchestration
  - [ ] 8.1 Implement RAG Pipeline
    - Implement `RAGPipeline` class with `MIN_QUERY_LENGTH=10`, `MAX_QUERY_LENGTH=500`
    - Implement query validation: empty check, length bounds, UTF-8 encoding validation
    - Implement `query()` method that orchestrates: validation → retrieval → generation
    - Implement query ID generation and performance timing
    - Implement query logging to `query_logs.jsonl` with timestamp, query, retrieved chunks, answer, tokens used
    - Implement error handling with stage identification
    - Handle empty retrieval results with Vietnamese message: "Không tìm thấy tài liệu liên quan đến câu hỏi của bạn"
    - Return `RAGResponse` with query_id, answer, source_chunks, relevance_scores, processing_time, model
    - _Requirements: 7.1, 7.2, 7.3, 10.1, 10.2, 10.3, 10.4, 10.5, 16.3_

  - [ ]* 8.2 Write property tests for RAG Pipeline
    - **Property 17: Query Length Validation**
    - **Property 25: Query Logging Completeness**
    - **Property 26: RAG Response Completeness**
    - **Property 45: UTF-8 Query Validation**
    - **Validates: Requirements 7.2, 10.4, 10.5, 16.3**

  - [ ]* 8.3 Write integration tests for RAG Pipeline
    - Test end-to-end query processing with sample Vietnamese queries
    - Test query validation error cases
    - Test handling of queries with no relevant documents
    - Test processing time meets < 5 second requirement
    - Verify query logging completeness
    - _Requirements: 7.1, 7.3, 10.1, 10.2, 10.3_

- [ ] 9. Evaluation framework implementation
  - [ ] 9.1 Implement evaluation metrics calculator
    - Implement `MetricsCalculator` class with static methods
    - Implement `precision_at_k()`: P@K = |retrieved[:k] ∩ relevant| / k
    - Implement `recall_at_k()`: R@K = |retrieved[:k] ∩ relevant| / |relevant|
    - Implement `mean_reciprocal_rank()`: MRR = 1 / rank(first_relevant_doc)
    - Implement `ndcg_at_k()`: DCG with relevance scores and logarithmic discount, normalized by ideal DCG
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 9.2 Write property tests for metrics calculator
    - **Property 27: Precision@K Bounds**
    - **Property 28: Recall@K Bounds**
    - **Property 29: MRR Bounds**
    - **Property 30: NDCG Bounds**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4**

  - [ ] 9.3 Implement evaluation framework
    - Implement `EvaluationDataset` dataclass with queries, ground_truth, relevance_scores
    - Implement `EvaluationDataset.from_json()` class method to load datasets
    - Implement `EvaluationFramework` class with `K_VALUES = [1, 3, 5, 10]`
    - Implement `evaluate()` method that runs all queries through retriever and computes metrics
    - Implement metric aggregation: compute mean and standard deviation across all queries
    - Implement `EvaluationReport` dataclass with `to_json()` and `print_summary()` methods
    - _Requirements: 11.5, 11.6, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [ ]* 9.4 Write property tests for Evaluation Framework
    - **Property 31: Evaluation K Coverage**
    - **Property 32: Evaluation Query Coverage**
    - **Property 33: Evaluation Report Completeness**
    - **Property 34: JSON Export Round-Trip**
    - **Validates: Requirements 11.5, 12.2, 12.5, 12.6**

  - [ ]* 9.5 Write unit tests for Evaluation Framework
    - Test metrics calculation with known datasets
    - Test edge cases: empty results, perfect ranking, no relevant documents
    - Test JSON import/export round-trip
    - Test report generation and summary formatting
    - _Requirements: 12.1, 12.3, 12.4_

- [ ] 10. Input validation and security
  - [ ] 10.1 Implement input validation utilities
    - Implement `InputValidator` class with static validation methods
    - Implement `validate_file_upload()`: check size (≤ 50MB), check extension ({.pdf, .docx, .txt})
    - Implement `sanitize_path()`: remove "..", "/", "\\", null bytes to prevent directory traversal
    - Implement `validate_query()`: check empty, length bounds [10, 500], UTF-8 encoding
    - Implement `validate_k_parameter()`: check type (int), bounds [1, 20]
    - Raise `ValidationError` with descriptive messages for all failures
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [ ]* 10.2 Write property tests for input validation
    - **Property 43: File Size Validation**
    - **Property 44: File Extension Validation**
    - **Property 46: Validation Error Messages**
    - **Property 47: Path Sanitization**
    - **Validates: Requirements 16.1, 16.2, 16.5, 16.6**

  - [ ]* 10.3 Write unit tests for input validation
    - Test file size edge cases (0 bytes, exactly 50MB, 50MB+1)
    - Test file extension case insensitivity
    - Test path sanitization with various attack vectors
    - Test query validation edge cases
    - Test error message descriptiveness
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

- [ ] 11. FastAPI endpoints and application setup
  - [ ] 11.1 Implement Pydantic request/response models
    - Define `QueryRequest` with query: str, k: int = 5
    - Define `QueryResponse` with query_id, answer, source_chunks, relevance_scores, processing_time
    - Define `IngestionResponse` with job_id, status, message
    - Define `StatusResponse` with job_id, status, chunk_count
    - Define `HealthResponse` with status, embedding_model_loaded, llm_model, vector_store_connected
    - _Requirements: 13.1, 13.2, 13.3, 13.5, 13.6_

  - [ ] 11.2 Implement FastAPI endpoints
    - Implement `POST /documents` for document ingestion with file upload validation
    - Implement `POST /query` for RAG query processing with request validation
    - Implement `GET /status/{job_id}` for ingestion status checking
    - Implement `GET /health` for system health checks
    - Add error handling: 400 for validation errors, 404 for not found, 500 for internal errors
    - Add request/response logging using structured logger
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 15.5, 16.5_

  - [ ]* 11.3 Write property tests for API endpoints
    - **Property 35: Job ID Assignment**
    - **Property 36: Query Response Structure**
    - **Property 41: API Request Logging**
    - **Validates: Requirements 13.4, 13.5, 15.5**

  - [ ] 11.4 Implement application startup and lifecycle
    - Implement `startup_event()` function that initializes all components
    - Validate configuration on startup
    - Load VietAI embedding model
    - Connect to ChromaDB vector store
    - Initialize OpenAI LLM service
    - Create global instances of ingestion_pipeline and rag_pipeline
    - Add startup event handler to FastAPI app
    - Implement graceful error handling for startup failures
    - _Requirements: 14.7, 15.1_

  - [ ]* 11.5 Write integration tests for API endpoints
    - Test document upload endpoint with various file types
    - Test query endpoint with sample Vietnamese queries
    - Test status endpoint for tracking ingestion progress
    - Test health endpoint reports correct component status
    - Test error handling for invalid inputs
    - Test request logging completeness
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 15.5_

- [ ] 12. Logging and monitoring enhancements
  - [ ] 12.1 Implement comprehensive logging decorators
    - Implement `log_performance()` decorator for timing operations
    - Apply performance logging to: document_ingestion, query_processing, embedding_generation, vector_search
    - Implement sensitive data redaction for API keys in logs
    - Implement `redact_api_key()` helper function
    - Verify all log entries include timestamp, component name, and operation details
    - _Requirements: 15.1, 15.4, 15.6_

  - [ ]* 12.2 Write property tests for logging
    - **Property 38: Error Log Completeness**
    - **Property 39: Log Severity Validity**
    - **Property 40: Performance Metrics Logging**
    - **Property 42: Sensitive Data Redaction**
    - **Validates: Requirements 15.1, 15.2, 15.4, 15.6**

  - [ ]* 12.3 Write unit tests for logging
    - Test structured logging format (JSON output)
    - Test log redaction for various sensitive patterns
    - Test performance decorator timing accuracy
    - Test log levels are used appropriately
    - _Requirements: 15.1, 15.2, 15.4, 15.6_

- [ ] 13. Checkpoint - Verify complete system
  - Run all unit tests, property tests, and integration tests
  - Test end-to-end workflow: upload document → ingest → query → receive answer
  - Test evaluation framework with sample dataset
  - Verify all configuration parameters work correctly
  - Test health check endpoint reports all components healthy
  - Review logs for completeness and proper redaction
  - Ask the user if questions arise

- [ ] 14. Documentation and deployment preparation
  - [ ] 14.1 Create deployment documentation
    - Create README.md with system overview, features, and architecture diagram
    - Document installation instructions: Python version, dependencies, environment setup
    - Document configuration parameters and .env file setup
    - Document API endpoint usage with curl examples
    - Document evaluation framework usage
    - Create requirements.txt with all dependencies and pinned versions
    - _Requirements: All (deployment support)_

  - [ ] 14.2 Create sample evaluation dataset
    - Create sample evaluation dataset in JSON format with Vietnamese queries
    - Include ground truth relevant document IDs
    - Include relevance scores (0-3 scale) for ranking evaluation
    - Document dataset format and usage
    - _Requirements: 11.6, 12.1_

  - [ ] 14.3 Create startup script and deployment guide
    - Create startup script that validates environment before running
    - Document model download instructions for VietAI embedding model
    - Document ChromaDB setup and persistence configuration
    - Document OpenAI API key setup
    - Create example systemd service file for production deployment
    - _Requirements: 14.7, 15.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Implementation uses Python with FastAPI framework
- VietAI/vit5-base-vietnamese-embedding model will be loaded locally or downloaded from Hugging Face
- ChromaDB provides persistent vector storage with cosine similarity
- OpenAI GPT-3.5-turbo or GPT-4 for answer generation
- Property-based tests verify universal correctness properties across randomized inputs
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end workflows
- Checkpoints ensure incremental validation of major milestones
- All Vietnamese text processing preserves diacritical marks and uses UTF-8 encoding

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "10.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "10.2", "10.3"] },
    { "id": 3, "tasks": ["2.4", "2.5"] },
    { "id": 4, "tasks": ["2.6", "2.7", "3.1"] },
    { "id": 5, "tasks": ["3.2", "3.3", "4.1"] },
    { "id": 6, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 7, "tasks": ["5.2", "5.3", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3"] },
    { "id": 9, "tasks": ["7.4", "7.5", "8.1"] },
    { "id": 10, "tasks": ["8.2", "8.3", "9.1"] },
    { "id": 11, "tasks": ["9.2", "9.3"] },
    { "id": 12, "tasks": ["9.4", "9.5", "11.1"] },
    { "id": 13, "tasks": ["11.2", "11.4"] },
    { "id": 14, "tasks": ["11.3", "11.5", "12.1"] },
    { "id": 15, "tasks": ["12.2", "12.3"] },
    { "id": 16, "tasks": ["14.1", "14.2", "14.3"] }
  ]
}
```
