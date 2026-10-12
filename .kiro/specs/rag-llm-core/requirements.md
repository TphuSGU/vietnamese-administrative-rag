# Requirements Document

## Introduction

This document specifies requirements for a simplified RAG (Retrieval-Augmented Generation) LLM core system designed for Vietnamese government documents. The system ingests Vietnamese text documents, converts them to vector embeddings using VietAI models, stores them in a vector database, and provides a RAG-based question-answering pipeline using OpenAI's GPT models. The system includes an evaluation framework to measure retrieval quality using standard information retrieval metrics.

## Glossary

- **Document_Ingestion_Pipeline**: The subsystem responsible for loading, cleaning, chunking, and embedding documents
- **Document_Loader**: Component that reads documents from supported file formats
- **Text_Cleaner**: Component that normalizes and preprocesses Vietnamese text
- **Semantic_Chunker**: Component that splits documents into semantically meaningful chunks while preserving structure
- **Embedding_Service**: Service that converts text chunks to 768-dimensional vectors using VietAI/vit5-base-vietnamese-embedding
- **Vector_Store**: Database that stores and indexes document embeddings for similarity search
- **RAG_Pipeline**: The end-to-end system that retrieves relevant chunks and generates answers using LLM
- **Retriever**: Component that performs similarity search to find relevant document chunks
- **LLM_Service**: Service that interfaces with OpenAI GPT models for answer generation
- **Evaluation_Framework**: Subsystem that measures retrieval quality using IR metrics
- **Chunk**: A semantically meaningful segment of text with metadata
- **Query**: A natural language question in Vietnamese
- **Context**: Retrieved document chunks provided to the LLM for answer generation
- **K**: The number of top results to retrieve in similarity search

## Requirements

### Requirement 1: Document Ingestion

**User Story:** As a system operator, I want to ingest Vietnamese government documents in various formats, so that they can be processed and made searchable through the RAG system.

#### Acceptance Criteria

1. THE Document_Loader SHALL accept documents in PDF, DOCX, and TXT formats
2. WHEN a document is loaded, THE Document_Loader SHALL extract text content with UTF-8 encoding
3. WHEN text extraction fails, THE Document_Loader SHALL return an error message identifying the failed document
4. THE Document_Loader SHALL preserve document metadata including filename, upload timestamp, and file size
5. WHEN a document is successfully loaded, THE Document_Loader SHALL pass the text content to the Text_Cleaner

### Requirement 2: Text Preprocessing

**User Story:** As a system operator, I want Vietnamese text to be properly cleaned and normalized, so that embedding quality is consistent across documents.

#### Acceptance Criteria

1. THE Text_Cleaner SHALL normalize Unicode characters to NFC form for Vietnamese text
2. THE Text_Cleaner SHALL remove excessive whitespace while preserving paragraph boundaries
3. THE Text_Cleaner SHALL preserve Vietnamese diacritical marks
4. WHEN control characters are encountered, THE Text_Cleaner SHALL remove them except for newlines and tabs
5. THE Text_Cleaner SHALL convert all text to lowercase for consistency
6. WHEN cleaning is complete, THE Text_Cleaner SHALL pass normalized text to the Semantic_Chunker

### Requirement 3: Semantic Chunking

**User Story:** As a system operator, I want documents to be split into semantically meaningful chunks, so that retrieval provides relevant context without fragmenting information.

#### Acceptance Criteria

1. THE Semantic_Chunker SHALL split text at paragraph boundaries as the primary chunking method
2. THE Semantic_Chunker SHALL preserve section headings within chunks for context
3. WHEN a paragraph exceeds 1000 characters, THE Semantic_Chunker SHALL split it at sentence boundaries
4. WHEN a sentence exceeds 1000 characters, THE Semantic_Chunker SHALL split it at clause boundaries
5. THE Semantic_Chunker SHALL create chunks between 200 and 1000 characters in length
6. THE Semantic_Chunker SHALL include metadata for each chunk containing source document ID, chunk index, and heading context
7. WHEN chunking is complete, THE Semantic_Chunker SHALL pass chunks to the Embedding_Service

### Requirement 4: Embedding Generation

**User Story:** As a system operator, I want text chunks to be converted to high-quality Vietnamese embeddings, so that semantic similarity search can find relevant content.

#### Acceptance Criteria

1. THE Embedding_Service SHALL use the VietAI/vit5-base-vietnamese-embedding model for all embeddings
2. WHEN a chunk is received, THE Embedding_Service SHALL generate a 768-dimensional dense vector
3. THE Embedding_Service SHALL batch process up to 32 chunks simultaneously for efficiency
4. WHEN embedding generation fails for a chunk, THE Embedding_Service SHALL log the error and continue with remaining chunks
5. THE Embedding_Service SHALL normalize embedding vectors to unit length for cosine similarity computation
6. WHEN embeddings are generated, THE Embedding_Service SHALL pass vectors and metadata to the Vector_Store

### Requirement 5: Vector Storage

**User Story:** As a system operator, I want embeddings to be stored efficiently with fast similarity search, so that retrieval provides quick responses.

#### Acceptance Criteria

1. THE Vector_Store SHALL store 768-dimensional embeddings with associated chunk text and metadata
2. THE Vector_Store SHALL support cosine similarity search
3. WHEN a similarity query is received, THE Vector_Store SHALL return the top K most similar chunks within 500 milliseconds for collections up to 10,000 documents
4. THE Vector_Store SHALL maintain an index optimized for Vietnamese embedding dimensions
5. THE Vector_Store SHALL support adding new document embeddings without rebuilding the entire index
6. WHEN a document is deleted, THE Vector_Store SHALL remove all associated chunk embeddings

### Requirement 6: Document Ingestion Pipeline Orchestration

**User Story:** As a system operator, I want the complete ingestion pipeline to execute automatically, so that documents become searchable without manual intervention.

#### Acceptance Criteria

1. WHEN a document is submitted for ingestion, THE Document_Ingestion_Pipeline SHALL execute loading, cleaning, chunking, embedding, and storage in sequence
2. IF any pipeline stage fails, THEN THE Document_Ingestion_Pipeline SHALL log the error with stage identification and document details
3. WHEN ingestion completes successfully, THE Document_Ingestion_Pipeline SHALL return the number of chunks created and stored
4. THE Document_Ingestion_Pipeline SHALL support processing multiple documents concurrently with up to 4 parallel pipelines
5. THE Document_Ingestion_Pipeline SHALL track ingestion status for each document as pending, processing, completed, or failed

### Requirement 7: Query Processing

**User Story:** As an end user, I want to ask questions in Vietnamese about government documents, so that I can receive accurate answers based on relevant content.

#### Acceptance Criteria

1. THE RAG_Pipeline SHALL accept natural language queries in Vietnamese
2. WHEN a query is received, THE RAG_Pipeline SHALL validate that query length is between 10 and 500 characters
3. IF query validation fails, THEN THE RAG_Pipeline SHALL return an error message requesting a properly formatted query
4. THE RAG_Pipeline SHALL embed the query using the same Embedding_Service used for documents
5. WHEN query embedding is complete, THE RAG_Pipeline SHALL pass the query vector to the Retriever

### Requirement 8: Retrieval

**User Story:** As an end user, I want the system to find the most relevant document chunks for my question, so that the generated answer is grounded in actual document content.

#### Acceptance Criteria

1. WHEN a query vector is received, THE Retriever SHALL search the Vector_Store for the top K similar chunks
2. THE Retriever SHALL use K=5 as the default number of chunks to retrieve
3. WHERE a custom K value is specified, THE Retriever SHALL accept K values between 1 and 20
4. THE Retriever SHALL return chunks sorted by similarity score in descending order
5. THE Retriever SHALL include similarity scores with each retrieved chunk
6. WHEN retrieval completes, THE Retriever SHALL pass retrieved chunks to the LLM_Service

### Requirement 9: Answer Generation

**User Story:** As an end user, I want the system to generate accurate answers using retrieved context, so that I receive informative responses grounded in government documents.

#### Acceptance Criteria

1. THE LLM_Service SHALL use OpenAI GPT-3.5-turbo or GPT-4 models for answer generation
2. WHEN retrieved chunks are received, THE LLM_Service SHALL format them into a context prompt with chunk separators
3. THE LLM_Service SHALL construct a prompt containing the query and retrieved context with instructions to answer based on provided documents
4. THE LLM_Service SHALL include instructions to respond in Vietnamese
5. WHEN the LLM cannot answer based on provided context, THE LLM_Service SHALL return a message stating that sufficient information is not available
6. THE LLM_Service SHALL limit generated answers to 500 tokens maximum
7. WHEN answer generation completes, THE LLM_Service SHALL return the answer text and source chunk references

### Requirement 10: RAG Pipeline Orchestration

**User Story:** As an end user, I want the complete RAG process to execute seamlessly, so that I receive answers quickly without understanding internal system operations.

#### Acceptance Criteria

1. WHEN a query is submitted, THE RAG_Pipeline SHALL execute query validation, embedding, retrieval, and generation in sequence
2. THE RAG_Pipeline SHALL complete end-to-end query processing within 5 seconds for standard queries
3. IF any pipeline stage fails, THEN THE RAG_Pipeline SHALL return an error response identifying the failure stage
4. THE RAG_Pipeline SHALL log each query with timestamp, retrieved chunks, and generated answer for evaluation purposes
5. THE RAG_Pipeline SHALL return a response containing the answer, source chunks, and relevance scores

### Requirement 11: Evaluation Framework - Retrieval Metrics

**User Story:** As a system developer, I want to measure retrieval quality using standard IR metrics, so that I can assess and improve system performance.

#### Acceptance Criteria

1. THE Evaluation_Framework SHALL compute Precision@K for retrieved results against ground truth relevant documents
2. THE Evaluation_Framework SHALL compute Recall@K for retrieved results against ground truth relevant documents
3. THE Evaluation_Framework SHALL compute Mean Reciprocal Rank (MRR) for the first relevant document position
4. THE Evaluation_Framework SHALL compute Normalized Discounted Cumulative Gain (NDCG) to measure ranking quality
5. WHERE K is specified, THE Evaluation_Framework SHALL compute metrics for K values of 1, 3, 5, and 10
6. THE Evaluation_Framework SHALL accept evaluation datasets containing queries, ground truth relevant document IDs, and relevance scores

### Requirement 12: Evaluation Framework - Testing Interface

**User Story:** As a system developer, I want to run evaluation tests on the RAG system, so that I can quantify retrieval performance with test datasets.

#### Acceptance Criteria

1. THE Evaluation_Framework SHALL accept a test dataset containing query-document pairs with relevance labels
2. WHEN an evaluation run is initiated, THE Evaluation_Framework SHALL execute all queries through the Retriever
3. THE Evaluation_Framework SHALL compare retrieved results against ground truth for each query
4. THE Evaluation_Framework SHALL aggregate metrics across all test queries to compute mean and standard deviation
5. WHEN evaluation completes, THE Evaluation_Framework SHALL return a report containing all computed metrics
6. THE Evaluation_Framework SHALL support exporting evaluation results to JSON format

### Requirement 13: Simple Testing API

**User Story:** As a system developer, I want a simple HTTP API to test the RAG system, so that I can validate functionality without building a complete application.

#### Acceptance Criteria

1. THE System SHALL provide a POST endpoint for document ingestion that accepts file uploads
2. THE System SHALL provide a POST endpoint for querying that accepts JSON with a query field
3. THE System SHALL provide a GET endpoint for retrieval status that returns ingestion pipeline status
4. WHEN a document is uploaded, THE System SHALL return an ingestion job ID
5. WHEN a query is submitted, THE System SHALL return JSON containing the answer, source chunks, and scores
6. THE System SHALL provide a GET endpoint for health checks that returns system status and model availability

### Requirement 14: Configuration Management

**User Story:** As a system operator, I want to configure system parameters without code changes, so that I can tune performance for different use cases.

#### Acceptance Criteria

1. THE System SHALL load configuration from environment variables or a configuration file
2. THE System SHALL support configuration of the OpenAI API key for LLM access
3. THE System SHALL support configuration of the VietAI model path for embeddings
4. THE System SHALL support configuration of chunk size limits with minimum and maximum values
5. THE System SHALL support configuration of retrieval K value as a default parameter
6. THE System SHALL support configuration of Vector_Store connection parameters
7. WHEN configuration is invalid or incomplete, THE System SHALL log an error and refuse to start

### Requirement 15: Error Handling and Logging

**User Story:** As a system operator, I want comprehensive error handling and logging, so that I can diagnose issues and monitor system health.

#### Acceptance Criteria

1. WHEN an error occurs in any component, THE System SHALL log the error with timestamp, component name, and error details
2. THE System SHALL use structured logging with severity levels of DEBUG, INFO, WARNING, and ERROR
3. IF an external service is unavailable, THEN THE System SHALL log the service name and retry up to 3 times with exponential backoff
4. THE System SHALL log performance metrics including processing time for ingestion and query operations
5. THE System SHALL log all API requests with endpoint, parameters, and response status
6. WHERE sensitive information appears in logs, THE System SHALL redact API keys and user data

### Requirement 16: Input Validation

**User Story:** As a system operator, I want robust input validation, so that invalid data does not corrupt the system or cause crashes.

#### Acceptance Criteria

1. THE System SHALL validate that uploaded documents do not exceed 50 MB in size
2. THE System SHALL validate that uploaded documents have supported file extensions
3. THE System SHALL validate that query text contains valid UTF-8 encoded Vietnamese characters
4. THE System SHALL validate that retrieval K parameter is a positive integer within allowed range
5. IF validation fails, THEN THE System SHALL return an error response with a descriptive message identifying the validation failure
6. THE System SHALL sanitize file paths to prevent directory traversal attacks
