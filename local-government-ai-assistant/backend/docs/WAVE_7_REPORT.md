# Wave 7: Document Ingestion Pipeline Orchestration

## Overview

Wave 7 implements the complete document ingestion pipeline that orchestrates all stages from loading documents to storing embeddings in the vector database. This pipeline coordinates the Loader, Cleaner, Chunker, Embedding Service, and Vector Store components.

## Components Implemented

### 1. IngestionJob Class

**Purpose**: Track individual ingestion jobs throughout the pipeline.

**Attributes**:
- `job_id`: Unique identifier for the job
- `document_path`: Path to the source document
- `status`: Current status (PENDING, PROCESSING, COMPLETED, FAILED)
- `started_at`: Timestamp when processing began
- `completed_at`: Timestamp when processing ended
- `error`: Error message if failed
- `chunk_count`: Number of chunks created
- `document_id`: Document identifier

### 2. IngestionStatusTracker Class

**Purpose**: Thread-safe status tracking for concurrent ingestion jobs.

**Features**:
- Async/await support with `asyncio.Lock`
- Create, update, and retrieve job status
- Thread-safe concurrent access

**Key Methods**:
```python
async def create_job(job_id: str, document_path: str) -> IngestionJob
async def update_status(job_id: str, status: IngestionStatus, **kwargs) -> None
async def get_job(job_id: str) -> Optional[IngestionJob]
```

### 3. DocumentIngestionPipeline Class

**Purpose**: Orchestrate the complete ingestion workflow.

**Pipeline Stages**:
1. **Load**: Extract text from PDF/DOCX/TXT files
2. **Clean**: Normalize and clean Vietnamese text
3. **Chunk**: Split into semantic chunks (200-1000 chars)
4. **Embed**: Generate 768-dim embeddings
5. **Store**: Save to ChromaDB vector store

**Concurrency Control**:
- Maximum 4 concurrent pipelines (Requirement 6.4)
- Uses `asyncio.Semaphore(4)` for limiting parallel execution

**Error Handling**:
- Stage-specific error identification
- Comprehensive logging with stage information
- Graceful failure with status updates

## API Reference

### DocumentIngestionPipeline

```python
class DocumentIngestionPipeline:
    def __init__(
        self,
        loader: DocumentLoader,
        cleaner: TextCleaner,
        chunker: SemanticChunker,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    )
```

#### Methods

**`async def ingest_document(file_path: Path) -> IngestionResult`**

Ingest a document through the complete pipeline.

**Parameters**:
- `file_path`: Path to document (PDF/DOCX/TXT)

**Returns**:
- `IngestionResult` with:
  - `job_id`: Unique job identifier
  - `status`: Final status (COMPLETED/FAILED)
  - `chunk_count`: Number of chunks created
  - `document_id`: Document identifier
  - `error_message`: Error details if failed

**Example**:
```python
pipeline = DocumentIngestionPipeline(
    loader=DocumentLoader(),
    cleaner=TextCleaner(),
    chunker=SemanticChunker(),
    embedding_service=EmbeddingService(),
    vector_store=VectorStore()
)

result = await pipeline.ingest_document(Path("document.pdf"))
print(f"Status: {result.status}, Chunks: {result.chunk_count}")
```

**`async def get_status(job_id: str) -> Optional[IngestionJob]`**

Get current status of an ingestion job.

**`async def get_result(job_id: str) -> Optional[IngestionResult]`**

Get final result for a completed job.

## Requirements Validated

✅ **Requirement 6.1**: Pipeline executes loading, cleaning, chunking, embedding, and storage in sequence  
✅ **Requirement 6.2**: Error logging with stage identification and document details  
✅ **Requirement 6.3**: Returns chunk count on successful completion  
✅ **Requirement 6.4**: Supports 4 parallel pipelines with semaphore control  
✅ **Requirement 6.5**: Status tracking (pending, processing, completed, failed)  

## Usage Example

### Basic Ingestion

```python
import asyncio
from pathlib import Path
from app.rag.ingestion.pipeline import DocumentIngestionPipeline
from app.rag.ingestion.loader import DocumentLoader
from app.rag.ingestion.cleaner import TextCleaner
from app.rag.ingestion.chunker import SemanticChunker
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore

# Initialize components
pipeline = DocumentIngestionPipeline(
    loader=DocumentLoader(),
    cleaner=TextCleaner(),
    chunker=SemanticChunker(min_size=200, max_size=1000),
    embedding_service=EmbeddingService(),
    vector_store=VectorStore()
)

# Ingest document
async def main():
    result = await pipeline.ingest_document(Path("van-ban-hanh-chinh.pdf"))
    
    if result.status == IngestionStatus.COMPLETED:
        print(f"✓ Ingested successfully")
        print(f"  Job ID: {result.job_id}")
        print(f"  Document ID: {result.document_id}")
        print(f"  Chunks created: {result.chunk_count}")
    else:
        print(f"✗ Ingestion failed: {result.error_message}")

asyncio.run(main())
```

### Concurrent Ingestion

```python
# Ingest multiple documents concurrently
async def ingest_multiple():
    files = [
        Path("doc1.pdf"),
        Path("doc2.pdf"),
        Path("doc3.pdf"),
        Path("doc4.pdf")
    ]
    
    tasks = [pipeline.ingest_document(f) for f in files]
    results = await asyncio.gather(*tasks)
    
    for result in results:
        print(f"Document {result.document_id}: {result.status}")

asyncio.run(ingest_multiple())
```

### Status Tracking

```python
# Track ingestion progress
async def track_ingestion():
    result = await pipeline.ingest_document(Path("large-document.pdf"))
    job_id = result.job_id
    
    # Check status
    job = await pipeline.get_status(job_id)
    print(f"Status: {job.status}")
    print(f"Started: {job.started_at}")
    print(f"Completed: {job.completed_at}")
    print(f"Chunks: {job.chunk_count}")

asyncio.run(track_ingestion())
```

## Error Handling

The pipeline provides detailed error messages identifying the failed stage:

| Error Message | Stage | Likely Cause |
|--------------|-------|--------------|
| `Stage 1 (Load) failed` | Document Loading | Corrupted file, unsupported format |
| `Stage 2 (Clean) failed` | Text Cleaning | Invalid Unicode, processing error |
| `Stage 3 (Chunk) failed` | Chunking | Empty text, chunking algorithm error |
| `Stage 4 (Embed) failed` | Embedding | Model error, invalid text |
| `Stage 5 (Store) failed` | Vector Storage | Database connection, storage error |

## Performance Characteristics

- **Concurrency**: Up to 4 documents processed simultaneously
- **Memory**: Scales with document size and batch processing
- **Throughput**: ~10-20 documents per minute (depending on size)
- **Logging**: Comprehensive logging at each stage

## Testing

8 integration tests covering:
- ✅ End-to-end PDF ingestion
- ✅ Failure recovery at each stage
- ✅ Concurrent ingestion (4 parallel jobs)
- ✅ Status tracking throughout pipeline
- ✅ Empty chunks failure
- ✅ Result retrieval

Run tests:
```bash
pytest tests/integration/test_ingestion_pipeline.py -v
```

## Next Steps

Wave 7 pipeline is integrated with Wave 8 (Retrieval) and Wave 9 (Generation) in the complete RAG system.

See `WAVE_10_REPORT.md` for RAG Pipeline orchestration.
