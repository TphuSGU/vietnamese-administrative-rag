# Design Document: RAG LLM Core System

## Overview

This document describes the design of a Retrieval-Augmented Generation (RAG) system optimized for Vietnamese government documents. The system uses VietAI embedding models for semantic search and OpenAI GPT models for answer generation, with a comprehensive evaluation framework for measuring retrieval quality.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
        ┌───────▼────────┐            ┌────────▼─────────┐
        │   Ingestion    │            │   RAG Pipeline   │
        │    Pipeline    │            │                  │
        └───────┬────────┘            └────────┬─────────┘
                │                               │
    ┌───────────┼───────────┐          ┌───────┼──────────┐
    │           │           │          │       │          │
┌───▼───┐  ┌───▼────┐  ┌──▼───┐  ┌───▼────┐ │   ┌─────▼─────┐
│Loader │  │Cleaner │  │Chunker│  │Retriever│ │   │LLM Service│
└───┬───┘  └───┬────┘  └──┬───┘  └───┬────┘ │   └─────┬─────┘
    │          │           │          │      │         │
    └──────────┴───────────┴──────────┘      │         │
                    │                         │         │
            ┌───────▼───────┐                 │         │
            │   Embedding   │◄────────────────┘         │
            │    Service    │                           │
            └───────┬───────┘                           │
                    │                                   │
            ┌───────▼────────┐                          │
            │  Vector Store  │                          │
            │   (ChromaDB)   │                          │
            └────────────────┘                          │
                                                        │
                                            ┌───────────▼──────────┐
                                            │   OpenAI GPT API     │
                                            └──────────────────────┘
```

### Component Relationships

- **Document Ingestion Pipeline**: Orchestrates the sequential processing of documents through loader → cleaner → chunker → embedding service → vector store
- **RAG Pipeline**: Orchestrates query processing through embedding service → retriever → LLM service
- **Embedding Service**: Shared component used by both ingestion and query pipelines
- **Vector Store**: Central repository for all document embeddings, queried by retriever
- **Evaluation Framework**: Standalone system that uses the retriever to compute IR metrics

## Core Components

### 1. Document Loader

**Purpose**: Load documents from various file formats and extract text content.

**Implementation**:
```python
class DocumentLoader:
    """Loads documents and extracts text content."""
    
    SUPPORTED_FORMATS = {'.pdf', '.docx', '.txt'}
    
    async def load_document(self, file_path: Path) -> Document:
        """
        Load a document and extract text content.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Document object with text and metadata
            
        Raises:
            UnsupportedFormatError: If file format is not supported
            ExtractionError: If text extraction fails
        """
```

**Key Features**:
- Support for PDF (using PyPDF2 or pdfplumber), DOCX (python-docx), and TXT formats
- UTF-8 encoding enforcement for all extracted text
- Metadata extraction: filename, timestamp, file size
- Error handling with descriptive messages identifying failed documents

**Dependencies**: PyPDF2/pdfplumber, python-docx, pathlib

### 2. Text Cleaner

**Purpose**: Normalize and preprocess Vietnamese text for consistent embedding quality.

**Implementation**:
```python
class TextCleaner:
    """Cleans and normalizes Vietnamese text."""
    
    def clean(self, text: str) -> str:
        """
        Clean and normalize Vietnamese text.
        
        Args:
            text: Raw text content
            
        Returns:
            Cleaned and normalized text
        """
```

**Cleaning Steps** (in order):
1. **Unicode Normalization**: Convert to NFC form using `unicodedata.normalize('NFC', text)`
2. **Control Character Removal**: Remove all control characters except `\n` and `\t`
3. **Whitespace Normalization**: Replace multiple spaces with single space, preserve paragraph breaks (double newlines)
4. **Diacritics Preservation**: Ensure Vietnamese diacritical marks remain intact (verified post-normalization)
5. **Lowercase Conversion**: Convert all text to lowercase for consistency

**Key Considerations**:
- Vietnamese diacritics (ă, â, ê, ô, ơ, ư, and tone marks: à, á, ả, ã, ạ, etc.) must be preserved
- Paragraph boundaries detected by double newlines (`\n\n`) must be maintained
- NFC normalization is idempotent: `normalize(normalize(x)) == normalize(x)`

### 3. Semantic Chunker

**Purpose**: Split documents into semantically meaningful chunks while preserving context.

**Implementation**:
```python
class SemanticChunker:
    """Splits text into semantic chunks with metadata."""
    
    MIN_CHUNK_SIZE = 200  # characters
    MAX_CHUNK_SIZE = 1000  # characters
    
    def chunk_text(
        self, 
        text: str, 
        document_id: str
    ) -> List[Chunk]:
        """
        Split text into semantic chunks.
        
        Args:
            text: Cleaned text to chunk
            document_id: Source document identifier
            
        Returns:
            List of Chunk objects with text and metadata
        """
```

**Chunking Algorithm**:

1. **Heading Detection**: Identify section headings using patterns:
   - Lines ending with `:` 
   - Lines in ALL CAPS
   - Lines matching "Điều X", "Chương X", "Phần X" patterns
   - Short lines (< 50 chars) followed by longer paragraphs

2. **Paragraph Splitting**: Split text at paragraph boundaries (`\n\n`)

3. **Size Enforcement**:
   - If paragraph < 200 chars: merge with next paragraph
   - If paragraph 200-1000 chars: keep as single chunk
   - If paragraph > 1000 chars: split at sentence boundaries
   - If sentence > 1000 chars: split at clause boundaries (commas, semicolons)

4. **Metadata Attachment**: Each chunk includes:
   ```python
   @dataclass
   class Chunk:
       text: str
       document_id: str
       chunk_index: int
       heading_context: Optional[str]  # Most recent heading before chunk
       char_start: int  # Position in original document
       char_end: int
   ```

**Vietnamese Sentence Detection**:
- Sentence endings: `.`, `!`, `?`, `;`
- Handle abbreviations: e.g., "v.v.", "tr.", "TP."
- Use regex: `r'[.!?;]\s+(?=[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])'`

### 4. Embedding Service

**Purpose**: Convert text chunks to dense vector embeddings using VietAI model.

**Implementation**:
```python
class EmbeddingService:
    """Generates embeddings using VietAI model."""
    
    MODEL_NAME = "VietAI/vit5-base-vietnamese-embedding"
    EMBEDDING_DIM = 768
    BATCH_SIZE = 32
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize embedding service.
        
        Args:
            model_path: Local path to model (optional, downloads if not provided)
        """
        self.model = self._load_model(model_path)
        self.tokenizer = self._load_tokenizer(model_path)
    
    async def embed_texts(
        self, 
        texts: List[str]
    ) -> List[np.ndarray]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of 768-dimensional embedding vectors (normalized)
        """
```

**Model Loading**:
```python
from transformers import AutoModel, AutoTokenizer
import torch

def _load_model(self, model_path: Optional[str]) -> AutoModel:
    path = model_path or self.MODEL_NAME
    model = AutoModel.from_pretrained(path)
    model.eval()  # Set to evaluation mode
    return model

def _load_tokenizer(self, model_path: Optional[str]) -> AutoTokenizer:
    path = model_path or self.MODEL_NAME
    return AutoTokenizer.from_pretrained(path)
```

**Embedding Generation**:
```python
def _generate_embeddings(
    self, 
    texts: List[str]
) -> np.ndarray:
    """Generate embeddings with mean pooling and normalization."""
    
    # Tokenize
    encoded = self.tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors='pt'
    )
    
    # Forward pass
    with torch.no_grad():
        outputs = self.model(**encoded)
    
    # Mean pooling
    attention_mask = encoded['attention_mask']
    token_embeddings = outputs.last_hidden_state
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    embeddings = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    # Normalize to unit length
    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    
    return embeddings.numpy()
```

**Batching Strategy**:
- Process up to 32 texts per batch
- Split larger lists into multiple batches
- Continue processing on individual chunk failure (log error and skip)

**Key Properties**:
- Output dimension: Always 768
- Normalization: L2 norm of output = 1.0
- Idempotent: Same text always produces same embedding

### 5. Vector Store

**Purpose**: Store and retrieve document embeddings using similarity search.

**Implementation**:
```python
class VectorStore:
    """ChromaDB-based vector storage for document embeddings."""
    
    def __init__(self, collection_name: str = "documents"):
        """Initialize ChromaDB client and collection."""
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
    
    async def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: List[np.ndarray]
    ) -> None:
        """Add chunk embeddings to vector store."""
    
    async def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5
    ) -> List[SearchResult]:
        """Search for similar chunks."""
    
    async def delete_document(self, document_id: str) -> None:
        """Remove all chunks from a document."""
```

**ChromaDB Configuration**:
```python
{
    "hnsw:space": "cosine",           # Cosine similarity metric
    "hnsw:construction_ef": 200,      # Construction time accuracy
    "hnsw:search_ef": 100,            # Query time accuracy
    "hnsw:M": 16                      # Number of connections per layer
}
```

**Data Schema**:
```python
# Stored in ChromaDB
{
    "ids": [str],                     # Unique chunk IDs: f"{document_id}_{chunk_index}"
    "embeddings": [List[float]],      # 768-dim vectors
    "documents": [str],                # Chunk text
    "metadatas": [{                    # Chunk metadata
        "document_id": str,
        "chunk_index": int,
        "heading_context": str,
        "char_start": int,
        "char_end": int,
        "timestamp": str
    }]
}
```

**Search Result**:
```python
@dataclass
class SearchResult:
    chunk_text: str
    similarity_score: float
    metadata: Dict[str, Any]
    chunk_id: str
```

**Key Features**:
- Incremental indexing: Add new documents without rebuilding
- Document deletion: Remove all chunks associated with a document ID
- Performance: < 500ms for 10,000 documents with K=5

### 6. Document Ingestion Pipeline

**Purpose**: Orchestrate the complete document ingestion process.

**Implementation**:
```python
class DocumentIngestionPipeline:
    """Orchestrates document ingestion from file to vector store."""
    
    def __init__(
        self,
        loader: DocumentLoader,
        cleaner: TextCleaner,
        chunker: SemanticChunker,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    ):
        self.loader = loader
        self.cleaner = cleaner
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.status_tracker = IngestionStatusTracker()
    
    async def ingest_document(
        self, 
        file_path: Path
    ) -> IngestionResult:
        """
        Ingest a document through the complete pipeline.
        
        Returns:
            IngestionResult with chunk count and status
        """
```

**Pipeline Flow**:
```python
async def ingest_document(self, file_path: Path) -> IngestionResult:
    job_id = self._generate_job_id()
    self.status_tracker.set_status(job_id, IngestionStatus.PENDING)
    
    try:
        self.status_tracker.set_status(job_id, IngestionStatus.PROCESSING)
        
        # Stage 1: Load
        document = await self.loader.load_document(file_path)
        
        # Stage 2: Clean
        cleaned_text = self.cleaner.clean(document.text)
        
        # Stage 3: Chunk
        chunks = self.chunker.chunk_text(cleaned_text, document.id)
        
        # Stage 4: Embed
        embeddings = await self.embedding_service.embed_texts(
            [chunk.text for chunk in chunks]
        )
        
        # Stage 5: Store
        await self.vector_store.add_chunks(chunks, embeddings)
        
        self.status_tracker.set_status(job_id, IngestionStatus.COMPLETED)
        
        return IngestionResult(
            job_id=job_id,
            status=IngestionStatus.COMPLETED,
            chunk_count=len(chunks),
            document_id=document.id
        )
        
    except Exception as e:
        logger.error(
            f"Ingestion failed at stage {self._current_stage}",
            extra={
                "job_id": job_id,
                "document": str(file_path),
                "error": str(e)
            }
        )
        self.status_tracker.set_status(job_id, IngestionStatus.FAILED)
        raise
```

**Status Tracking**:
```python
class IngestionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class IngestionStatusTracker:
    """Thread-safe status tracking for ingestion jobs."""
    
    def __init__(self):
        self._statuses: Dict[str, IngestionStatus] = {}
        self._lock = asyncio.Lock()
    
    async def set_status(self, job_id: str, status: IngestionStatus):
        async with self._lock:
            self._statuses[job_id] = status
    
    async def get_status(self, job_id: str) -> Optional[IngestionStatus]:
        async with self._lock:
            return self._statuses.get(job_id)
```

**Concurrency**:
- Support up to 4 concurrent ingestion pipelines
- Use asyncio semaphore for concurrency control:
```python
self._semaphore = asyncio.Semaphore(4)

async def ingest_document(self, file_path: Path) -> IngestionResult:
    async with self._semaphore:
        # ... ingestion logic ...
```

### 7. Retriever

**Purpose**: Search for relevant document chunks given a query embedding.

**Implementation**:
```python
class Retriever:
    """Retrieves relevant chunks from vector store."""
    
    DEFAULT_K = 5
    MIN_K = 1
    MAX_K = 20
    
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService
    ):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
    
    async def retrieve(
        self,
        query: str,
        k: int = DEFAULT_K
    ) -> List[RetrievedChunk]:
        """
        Retrieve top K similar chunks for a query.
        
        Args:
            query: Natural language query
            k: Number of chunks to retrieve (1-20)
            
        Returns:
            List of retrieved chunks sorted by similarity (descending)
        """
```

**Retrieval Flow**:
```python
async def retrieve(self, query: str, k: int = DEFAULT_K) -> List[RetrievedChunk]:
    # Validate K
    if not (self.MIN_K <= k <= self.MAX_K):
        raise ValueError(f"K must be between {self.MIN_K} and {self.MAX_K}")
    
    # Embed query
    query_embedding = await self.embedding_service.embed_texts([query])
    query_vector = query_embedding[0]
    
    # Search vector store
    results = await self.vector_store.search(query_vector, k=k)
    
    # Results are already sorted by similarity (descending)
    return [
        RetrievedChunk(
            text=r.chunk_text,
            similarity_score=r.similarity_score,
            metadata=r.metadata
        )
        for r in results
    ]
```

**Retrieved Chunk Structure**:
```python
@dataclass
class RetrievedChunk:
    text: str
    similarity_score: float
    metadata: Dict[str, Any]
    
    @property
    def document_id(self) -> str:
        return self.metadata['document_id']
    
    @property
    def heading_context(self) -> Optional[str]:
        return self.metadata.get('heading_context')
```

### 8. LLM Service

**Purpose**: Generate answers using OpenAI GPT models with retrieved context.

**Implementation**:
```python
class LLMService:
    """Generates answers using OpenAI GPT models."""
    
    MODEL = "gpt-3.5-turbo"  # or "gpt-4"
    MAX_TOKENS = 500
    
    def __init__(self, api_key: str, model: str = MODEL):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def generate_answer(
        self,
        query: str,
        retrieved_chunks: List[RetrievedChunk]
    ) -> GeneratedAnswer:
        """
        Generate an answer using retrieved context.
        
        Args:
            query: User's question
            retrieved_chunks: Context chunks from retrieval
            
        Returns:
            Generated answer with source references
        """
```

**Prompt Construction**:
```python
def _construct_prompt(
    self,
    query: str,
    chunks: List[RetrievedChunk]
) -> str:
    """Construct prompt with context and instructions."""
    
    # Format context
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        heading = f" ({chunk.heading_context})" if chunk.heading_context else ""
        context_parts.append(
            f"[Tài liệu {i}]{heading}:\n{chunk.text}"
        )
    
    context = "\n\n".join(context_parts)
    
    # Construct full prompt
    prompt = f"""Bạn là trợ lý AI hỗ trợ công dân tra cứu thông tin về văn bản chính quyền địa phương.

Dựa trên các tài liệu sau đây, hãy trả lời câu hỏi của người dùng bằng tiếng Việt.

Ngữ cảnh:
{context}

Câu hỏi: {query}

Hướng dẫn:
- Trả lời dựa HOÀN TOÀN trên thông tin trong các tài liệu được cung cấp
- Nếu thông tin không đủ để trả lời, hãy nói rõ "Thông tin trong tài liệu không đủ để trả lời câu hỏi này"
- Trích dẫn tài liệu liên quan khi trả lời (ví dụ: "Theo Tài liệu 1...")
- Trả lời ngắn gọn, rõ ràng bằng tiếng Việt

Trả lời:"""
    
    return prompt
```

**Answer Generation**:
```python
async def generate_answer(
    self,
    query: str,
    retrieved_chunks: List[RetrievedChunk]
) -> GeneratedAnswer:
    
    prompt = self._construct_prompt(query, retrieved_chunks)
    
    try:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Bạn là trợ lý AI trả lời câu hỏi về văn bản chính quyền."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.MAX_TOKENS,
            temperature=0.3,  # Low temperature for factual responses
        )
        
        answer_text = response.choices[0].message.content
        
        return GeneratedAnswer(
            answer=answer_text,
            source_chunks=[
                ChunkReference(
                    document_id=chunk.document_id,
                    text=chunk.text[:200],  # First 200 chars as preview
                    similarity_score=chunk.similarity_score
                )
                for chunk in retrieved_chunks
            ],
            model=self.model,
            tokens_used=response.usage.total_tokens
        )
        
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise LLMGenerationError(f"Failed to generate answer: {e}")
```

**Response Structure**:
```python
@dataclass
class GeneratedAnswer:
    answer: str
    source_chunks: List[ChunkReference]
    model: str
    tokens_used: int

@dataclass
class ChunkReference:
    document_id: str
    text: str  # Preview
    similarity_score: float
```

### 9. RAG Pipeline

**Purpose**: Orchestrate the complete query-to-answer pipeline.

**Implementation**:
```python
class RAGPipeline:
    """End-to-end RAG pipeline for query processing."""
    
    MIN_QUERY_LENGTH = 10
    MAX_QUERY_LENGTH = 500
    
    def __init__(
        self,
        retriever: Retriever,
        llm_service: LLMService
    ):
        self.retriever = retriever
        self.llm_service = llm_service
    
    async def query(
        self,
        query_text: str,
        k: int = 5
    ) -> RAGResponse:
        """
        Process a query through the RAG pipeline.
        
        Args:
            query_text: User's question in Vietnamese
            k: Number of chunks to retrieve
            
        Returns:
            RAG response with answer and metadata
        """
```

**Pipeline Flow with Error Handling**:
```python
async def query(self, query_text: str, k: int = 5) -> RAGResponse:
    start_time = time.time()
    query_id = self._generate_query_id()
    
    try:
        # Stage 1: Validation
        self._validate_query(query_text)
        
        # Stage 2: Retrieval
        retrieved_chunks = await self.retriever.retrieve(query_text, k=k)
        
        if not retrieved_chunks:
            return RAGResponse(
                query_id=query_id,
                answer="Không tìm thấy tài liệu liên quan đến câu hỏi của bạn.",
                source_chunks=[],
                processing_time=time.time() - start_time
            )
        
        # Stage 3: Generation
        generated_answer = await self.llm_service.generate_answer(
            query_text,
            retrieved_chunks
        )
        
        # Log for evaluation
        self._log_query(query_id, query_text, retrieved_chunks, generated_answer)
        
        processing_time = time.time() - start_time
        
        return RAGResponse(
            query_id=query_id,
            answer=generated_answer.answer,
            source_chunks=generated_answer.source_chunks,
            relevance_scores=[c.similarity_score for c in retrieved_chunks],
            processing_time=processing_time,
            model=generated_answer.model
        )
        
    except ValidationError as e:
        raise RAGValidationError(f"Query validation failed: {e}")
    except Exception as e:
        logger.error(
            f"RAG pipeline failed",
            extra={
                "query_id": query_id,
                "stage": self._current_stage,
                "error": str(e)
            }
        )
        raise RAGPipelineError(f"Pipeline failed at {self._current_stage}: {e}")

def _validate_query(self, query: str) -> None:
    """Validate query format and length."""
    if not query or not query.strip():
        raise ValidationError("Query cannot be empty")
    
    length = len(query)
    if not (self.MIN_QUERY_LENGTH <= length <= self.MAX_QUERY_LENGTH):
        raise ValidationError(
            f"Query length must be between {self.MIN_QUERY_LENGTH} "
            f"and {self.MAX_QUERY_LENGTH} characters"
        )
    
    # Validate UTF-8
    try:
        query.encode('utf-8')
    except UnicodeEncodeError:
        raise ValidationError("Query must be valid UTF-8 encoded text")
```

**Query Logging for Evaluation**:
```python
def _log_query(
    self,
    query_id: str,
    query: str,
    chunks: List[RetrievedChunk],
    answer: GeneratedAnswer
) -> None:
    """Log query for evaluation purposes."""
    log_entry = {
        "query_id": query_id,
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "retrieved_chunks": [
            {
                "document_id": c.document_id,
                "similarity_score": c.similarity_score,
                "text_preview": c.text[:100]
            }
            for c in chunks
        ],
        "answer": answer.answer,
        "tokens_used": answer.tokens_used
    }
    
    # Write to evaluation log file
    with open("query_logs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
```

**Response Structure**:
```python
@dataclass
class RAGResponse:
    query_id: str
    answer: str
    source_chunks: List[ChunkReference]
    relevance_scores: List[float]
    processing_time: float
    model: str
```

### 10. Evaluation Framework

**Purpose**: Measure retrieval quality using standard information retrieval metrics.

**Implementation**:
```python
class EvaluationFramework:
    """Evaluates retrieval quality using IR metrics."""
    
    K_VALUES = [1, 3, 5, 10]
    
    def __init__(self, retriever: Retriever):
        self.retriever = retriever
    
    async def evaluate(
        self,
        test_dataset: EvaluationDataset
    ) -> EvaluationReport:
        """
        Evaluate retrieval performance on a test dataset.
        
        Args:
            test_dataset: Dataset with queries and ground truth
            
        Returns:
            Comprehensive evaluation report with all metrics
        """
```

**Evaluation Dataset Format**:
```python
@dataclass
class EvaluationDataset:
    """Dataset for evaluation."""
    queries: List[str]
    ground_truth: Dict[str, List[str]]  # query -> list of relevant doc IDs
    relevance_scores: Dict[str, Dict[str, float]]  # query -> doc_id -> score [0-3]
    
    @classmethod
    def from_json(cls, path: Path) -> 'EvaluationDataset':
        """Load dataset from JSON file."""

# JSON format:
# {
#   "queries": ["Thủ tục đăng ký hộ khẩu?", ...],
#   "ground_truth": {
#     "Thủ tục đăng ký hộ khẩu?": ["doc_123", "doc_456"]
#   },
#   "relevance_scores": {
#     "Thủ tục đăng ký hộ khẩu?": {
#       "doc_123": 3,  # 0=not relevant, 1=marginally, 2=relevant, 3=highly relevant
#       "doc_456": 2
#     }
#   }
# }
```

**Metric Implementations**:

```python
class MetricsCalculator:
    """Calculates IR metrics."""
    
    @staticmethod
    def precision_at_k(
        retrieved: List[str],
        relevant: List[str],
        k: int
    ) -> float:
        """
        Precision@K: Proportion of top K results that are relevant.
        
        P@K = |retrieved[:k] ∩ relevant| / k
        """
        retrieved_k = retrieved[:k]
        relevant_set = set(relevant)
        hits = sum(1 for doc_id in retrieved_k if doc_id in relevant_set)
        return hits / k if k > 0 else 0.0
    
    @staticmethod
    def recall_at_k(
        retrieved: List[str],
        relevant: List[str],
        k: int
    ) -> float:
        """
        Recall@K: Proportion of relevant documents found in top K.
        
        R@K = |retrieved[:k] ∩ relevant| / |relevant|
        """
        if not relevant:
            return 0.0
        retrieved_k = retrieved[:k]
        relevant_set = set(relevant)
        hits = sum(1 for doc_id in retrieved_k if doc_id in relevant_set)
        return hits / len(relevant)
    
    @staticmethod
    def mean_reciprocal_rank(
        retrieved: List[str],
        relevant: List[str]
    ) -> float:
        """
        MRR: Reciprocal of the rank of the first relevant document.
        
        MRR = 1 / rank(first_relevant_doc)
        """
        relevant_set = set(relevant)
        for rank, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant_set:
                return 1.0 / rank
        return 0.0
    
    @staticmethod
    def ndcg_at_k(
        retrieved: List[str],
        relevance_scores: Dict[str, float],
        k: int
    ) -> float:
        """
        NDCG@K: Normalized Discounted Cumulative Gain.
        
        DCG@K = Σ(rel_i / log2(i+1)) for i in 1..k
        NDCG@K = DCG@K / IDCG@K
        
        where IDCG is the DCG of the ideal ranking.
        """
        retrieved_k = retrieved[:k]
        
        # Calculate DCG
        dcg = 0.0
        for i, doc_id in enumerate(retrieved_k, 1):
            rel = relevance_scores.get(doc_id, 0.0)
            dcg += rel / np.log2(i + 1)
        
        # Calculate IDCG (ideal DCG with perfect ranking)
        ideal_scores = sorted(relevance_scores.values(), reverse=True)[:k]
        idcg = sum(
            rel / np.log2(i + 1)
            for i, rel in enumerate(ideal_scores, 1)
        )
        
        return dcg / idcg if idcg > 0 else 0.0
```

**Evaluation Process**:
```python
async def evaluate(
    self,
    test_dataset: EvaluationDataset
) -> EvaluationReport:
    """Run evaluation on test dataset."""
    
    results_per_query = []
    
    # Process each query
    for query in test_dataset.queries:
        ground_truth = test_dataset.ground_truth[query]
        relevance = test_dataset.relevance_scores[query]
        
        # Retrieve documents (use max K for evaluation)
        retrieved_chunks = await self.retriever.retrieve(query, k=20)
        retrieved_ids = [chunk.metadata['document_id'] for chunk in retrieved_chunks]
        
        # Compute metrics for all K values
        query_metrics = {}
        for k in self.K_VALUES:
            query_metrics[k] = {
                'precision': MetricsCalculator.precision_at_k(retrieved_ids, ground_truth, k),
                'recall': MetricsCalculator.recall_at_k(retrieved_ids, ground_truth, k),
                'ndcg': MetricsCalculator.ndcg_at_k(retrieved_ids, relevance, k)
            }
        
        # MRR is not K-specific
        mrr = MetricsCalculator.mean_reciprocal_rank(retrieved_ids, ground_truth)
        
        results_per_query.append({
            'query': query,
            'metrics': query_metrics,
            'mrr': mrr
        })
    
    # Aggregate metrics across queries
    aggregated = self._aggregate_metrics(results_per_query)
    
    return EvaluationReport(
        dataset_size=len(test_dataset.queries),
        metrics_by_k=aggregated,
        per_query_results=results_per_query,
        timestamp=datetime.utcnow()
    )

def _aggregate_metrics(
    self,
    results: List[Dict]
) -> Dict[int, Dict[str, Dict[str, float]]]:
    """Aggregate metrics across queries."""
    
    aggregated = {}
    for k in self.K_VALUES:
        precision_values = [r['metrics'][k]['precision'] for r in results]
        recall_values = [r['metrics'][k]['recall'] for r in results]
        ndcg_values = [r['metrics'][k]['ndcg'] for r in results]
        
        aggregated[k] = {
            'precision': {
                'mean': np.mean(precision_values),
                'std': np.std(precision_values)
            },
            'recall': {
                'mean': np.mean(recall_values),
                'std': np.std(recall_values)
            },
            'ndcg': {
                'mean': np.mean(ndcg_values),
                'std': np.std(ndcg_values)
            }
        }
    
    # Add MRR
    mrr_values = [r['mrr'] for r in results]
    aggregated['mrr'] = {
        'mean': np.mean(mrr_values),
        'std': np.std(mrr_values)
    }
    
    return aggregated
```

**Report Structure**:
```python
@dataclass
class EvaluationReport:
    dataset_size: int
    metrics_by_k: Dict[int, Dict[str, Dict[str, float]]]
    per_query_results: List[Dict]
    timestamp: datetime
    
    def to_json(self, path: Path) -> None:
        """Export report to JSON file."""
        
    def print_summary(self) -> None:
        """Print human-readable summary."""
        print(f"Evaluation Report ({self.dataset_size} queries)")
        print("=" * 50)
        
        for k in [1, 3, 5, 10]:
            metrics = self.metrics_by_k[k]
            print(f"\nK = {k}")
            print(f"  Precision@{k}: {metrics['precision']['mean']:.3f} ± {metrics['precision']['std']:.3f}")
            print(f"  Recall@{k}:    {metrics['recall']['mean']:.3f} ± {metrics['recall']['std']:.3f}")
            print(f"  NDCG@{k}:      {metrics['ndcg']['mean']:.3f} ± {metrics['ndcg']['std']:.3f}")
        
        mrr = self.metrics_by_k['mrr']
        print(f"\nMRR: {mrr['mean']:.3f} ± {mrr['std']:.3f}")
```

## API Endpoints

### FastAPI Application Structure

```python
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel

app = FastAPI(title="RAG LLM Core API")

# Request/Response models
class QueryRequest(BaseModel):
    query: str
    k: int = 5

class QueryResponse(BaseModel):
    query_id: str
    answer: str
    source_chunks: List[Dict[str, Any]]
    relevance_scores: List[float]
    processing_time: float

class IngestionResponse(BaseModel):
    job_id: str
    status: str
    message: str

class StatusResponse(BaseModel):
    job_id: str
    status: str
    chunk_count: Optional[int] = None

class HealthResponse(BaseModel):
    status: str
    embedding_model_loaded: bool
    llm_model: str
    vector_store_connected: bool
```

### Endpoint Implementations

**1. Document Ingestion**
```python
@app.post("/documents", response_model=IngestionResponse)
async def ingest_document(
    file: UploadFile = File(...)
):
    """
    Ingest a document into the RAG system.
    
    - Accepts: PDF, DOCX, TXT files (max 50MB)
    - Returns: Job ID for status tracking
    """
    # Validate file size
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 50MB limit"
        )
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in {'.pdf', '.docx', '.txt'}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_ext}"
        )
    
    # Save temporarily
    temp_path = Path(f"/tmp/{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(content)
    
    # Start ingestion
    try:
        result = await ingestion_pipeline.ingest_document(temp_path)
        
        return IngestionResponse(
            job_id=result.job_id,
            status=result.status.value,
            message=f"Document ingestion started. Created {result.chunk_count} chunks."
        )
    finally:
        # Cleanup temp file
        temp_path.unlink(missing_ok=True)
```

**2. Query Processing**
```python
@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a query through the RAG pipeline.
    
    - Accepts: Vietnamese text query (10-500 characters)
    - Returns: Generated answer with source chunks
    """
    try:
        response = await rag_pipeline.query(
            query_text=request.query,
            k=request.k
        )
        
        return QueryResponse(
            query_id=response.query_id,
            answer=response.answer,
            source_chunks=[
                {
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "similarity_score": chunk.similarity_score
                }
                for chunk in response.source_chunks
            ],
            relevance_scores=response.relevance_scores,
            processing_time=response.processing_time
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail="Query processing failed")
```

**3. Status Check**
```python
@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_ingestion_status(job_id: str):
    """
    Check ingestion job status.
    
    - Returns: Current status and chunk count if completed
    """
    status = await ingestion_pipeline.get_status(job_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail="Job ID not found")
    
    result = await ingestion_pipeline.get_result(job_id)
    
    return StatusResponse(
        job_id=job_id,
        status=status.value,
        chunk_count=result.chunk_count if result else None
    )
```

**4. Health Check**
```python
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    System health check.
    
    - Returns: Model availability and system status
    """
    try:
        # Check embedding model
        embedding_loaded = embedding_service.model is not None
        
        # Check vector store
        vector_store_connected = await vector_store.health_check()
        
        # Check LLM
        llm_model = llm_service.model
        
        status = "healthy" if all([
            embedding_loaded,
            vector_store_connected,
            llm_model
        ]) else "degraded"
        
        return HealthResponse(
            status=status,
            embedding_model_loaded=embedding_loaded,
            llm_model=llm_model,
            vector_store_connected=vector_store_connected
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            embedding_model_loaded=False,
            llm_model="unknown",
            vector_store_connected=False
        )
```

## Configuration Management

### Configuration Schema

```python
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """Application configuration."""
    
    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-3.5-turbo", env="OPENAI_MODEL")
    
    # VietAI Embedding
    vietai_model_path: Optional[str] = Field(None, env="VIETAI_MODEL_PATH")
    
    # Chunking
    chunk_min_size: int = Field(200, env="CHUNK_MIN_SIZE")
    chunk_max_size: int = Field(1000, env="CHUNK_MAX_SIZE")
    
    # Retrieval
    default_k: int = Field(5, env="DEFAULT_K")
    max_k: int = Field(20, env="MAX_K")
    
    # Vector Store
    chroma_db_path: str = Field("./chroma_db", env="CHROMA_DB_PATH")
    chroma_collection: str = Field("documents", env="CHROMA_COLLECTION")
    
    # API
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Load settings
settings = Settings()
```

### Environment Variables (.env)

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo

# VietAI Model (optional, downloads if not provided)
VIETAI_MODEL_PATH=/path/to/local/model

# Chunking Parameters
CHUNK_MIN_SIZE=200
CHUNK_MAX_SIZE=1000

# Retrieval Parameters
DEFAULT_K=5
MAX_K=20

# Vector Store
CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION=documents

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
```

### Configuration Validation

```python
def validate_configuration(settings: Settings) -> None:
    """Validate configuration and fail fast."""
    
    errors = []
    
    # Check OpenAI API key
    if not settings.openai_api_key or settings.openai_api_key == "":
        errors.append("OPENAI_API_KEY is required")
    
    # Check chunk sizes
    if settings.chunk_min_size >= settings.chunk_max_size:
        errors.append(
            f"CHUNK_MIN_SIZE ({settings.chunk_min_size}) must be less than "
            f"CHUNK_MAX_SIZE ({settings.chunk_max_size})"
        )
    
    # Check K values
    if settings.default_k > settings.max_k:
        errors.append(
            f"DEFAULT_K ({settings.default_k}) cannot exceed "
            f"MAX_K ({settings.max_k})"
        )
    
    # Check VietAI model path if provided
    if settings.vietai_model_path:
        model_path = Path(settings.vietai_model_path)
        if not model_path.exists():
            errors.append(f"VietAI model path does not exist: {settings.vietai_model_path}")
    
    if errors:
        error_msg = "\n".join(f"  - {e}" for e in errors)
        logger.error(f"Configuration validation failed:\n{error_msg}")
        raise ValueError(f"Invalid configuration:\n{error_msg}")
```

## Error Handling

### Exception Hierarchy

```python
class RAGException(Exception):
    """Base exception for RAG system."""
    pass

class DocumentLoadError(RAGException):
    """Failed to load document."""
    pass

class EmbeddingError(RAGException):
    """Failed to generate embeddings."""
    pass

class VectorStoreError(RAGException):
    """Vector store operation failed."""
    pass

class RAGValidationError(RAGException):
    """Input validation failed."""
    pass

class RAGPipelineError(RAGException):
    """Pipeline execution failed."""
    pass

class LLMGenerationError(RAGException):
    """LLM answer generation failed."""
    pass
```

### Retry Strategy

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# Retry for external services
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((openai.APIError, openai.RateLimitError)),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying OpenAI call, attempt {retry_state.attempt_number}"
    )
)
async def call_openai_with_retry(...):
    """Call OpenAI API with retry logic."""
    pass
```

## Logging

### Structured Logging Setup

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """Structured JSON logger."""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level))
        
        # JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(self._create_formatter())
        self.logger.addHandler(handler)
    
    def _create_formatter(self):
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "component": record.name,
                    "message": record.getMessage(),
                }
                
                # Add extra fields
                if hasattr(record, 'extra'):
                    log_data.update(record.extra)
                
                # Redact sensitive data
                log_data = self._redact_sensitive(log_data)
                
                return json.dumps(log_data, ensure_ascii=False)
            
            def _redact_sensitive(self, data):
                """Redact API keys and sensitive information."""
                sensitive_keys = {'api_key', 'openai_api_key', 'password', 'token'}
                
                def redact_dict(d):
                    if isinstance(d, dict):
                        return {
                            k: '[REDACTED]' if k.lower() in sensitive_keys else redact_dict(v)
                            for k, v in d.items()
                        }
                    elif isinstance(d, str) and any(key in d.lower() for key in sensitive_keys):
                        # Redact in strings
                        return '[REDACTED]'
                    return d
                
                return redact_dict(data)
        
        return JSONFormatter()

# Initialize logger
logger = StructuredLogger("rag_system", level=settings.log_level).logger
```

### Performance Metrics Logging

```python
def log_performance(operation: str):
    """Decorator for logging operation performance."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"Operation completed: {operation}",
                    extra={
                        "operation": operation,
                        "duration_seconds": duration,
                        "status": "success"
                    }
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Operation failed: {operation}",
                    extra={
                        "operation": operation,
                        "duration_seconds": duration,
                        "status": "error",
                        "error": str(e)
                    }
                )
                raise
        return wrapper
    return decorator

# Usage
@log_performance("document_ingestion")
async def ingest_document(file_path: Path) -> IngestionResult:
    # ... implementation ...
```

## Security Considerations

### Input Validation

```python
class InputValidator:
    """Validates all user inputs."""
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
    
    @staticmethod
    def validate_file_upload(file: UploadFile, content: bytes) -> None:
        """Validate uploaded file."""
        
        # Check size
        if len(content) > InputValidator.MAX_FILE_SIZE:
            raise ValidationError(
                f"File size ({len(content)} bytes) exceeds limit "
                f"({InputValidator.MAX_FILE_SIZE} bytes)"
            )
        
        # Check extension
        ext = Path(file.filename).suffix.lower()
        if ext not in InputValidator.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File extension '{ext}' not allowed. "
                f"Allowed: {InputValidator.ALLOWED_EXTENSIONS}"
            )
        
        # Sanitize filename
        sanitized = InputValidator.sanitize_path(file.filename)
        if sanitized != file.filename:
            logger.warning(
                f"Filename sanitized: '{file.filename}' -> '{sanitized}'"
            )
    
    @staticmethod
    def sanitize_path(path: str) -> str:
        """Prevent directory traversal attacks."""
        # Remove directory traversal sequences
        sanitized = path.replace('..', '').replace('/', '_').replace('\\', '_')
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        return sanitized
    
    @staticmethod
    def validate_query(query: str) -> None:
        """Validate query input."""
        
        # Check not empty
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty")
        
        # Check length
        if len(query) < 10:
            raise ValidationError("Query must be at least 10 characters")
        if len(query) > 500:
            raise ValidationError("Query must not exceed 500 characters")
        
        # Check UTF-8 encoding
        try:
            query.encode('utf-8')
        except UnicodeEncodeError:
            raise ValidationError("Query must be valid UTF-8 text")
    
    @staticmethod
    def validate_k_parameter(k: int) -> None:
        """Validate retrieval K parameter."""
        if not isinstance(k, int):
            raise ValidationError("K must be an integer")
        if not (1 <= k <= 20):
            raise ValidationError("K must be between 1 and 20")
```

### API Key Management

```python
# Never log API keys
def redact_api_key(key: str) -> str:
    """Redact API key for logging."""
    if not key:
        return "[EMPTY]"
    if len(key) < 8:
        return "[REDACTED]"
    return f"{key[:4]}...{key[-4:]}"

# Log configuration without exposing secrets
logger.info(
    "Configuration loaded",
    extra={
        "openai_key": redact_api_key(settings.openai_api_key),
        "model": settings.openai_model,
        "chunk_size": f"{settings.chunk_min_size}-{settings.chunk_max_size}"
    }
)
```

## Data Models

### Complete Data Model Definitions

```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Document Models
@dataclass
class Document:
    """Loaded document with metadata."""
    id: str
    text: str
    filename: str
    file_size: int
    upload_timestamp: datetime
    format: str

# Chunk Models
@dataclass
class Chunk:
    """Text chunk with metadata."""
    text: str
    document_id: str
    chunk_index: int
    heading_context: Optional[str]
    char_start: int
    char_end: int

# Ingestion Models
class IngestionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class IngestionResult:
    job_id: str
    status: IngestionStatus
    chunk_count: int
    document_id: str
    error_message: Optional[str] = None

# Retrieval Models
@dataclass
class SearchResult:
    chunk_text: str
    similarity_score: float
    metadata: Dict[str, Any]
    chunk_id: str

@dataclass
class RetrievedChunk:
    text: str
    similarity_score: float
    metadata: Dict[str, Any]
    
    @property
    def document_id(self) -> str:
        return self.metadata['document_id']
    
    @property
    def heading_context(self) -> Optional[str]:
        return self.metadata.get('heading_context')

# Generation Models
@dataclass
class ChunkReference:
    document_id: str
    text: str
    similarity_score: float

@dataclass
class GeneratedAnswer:
    answer: str
    source_chunks: List[ChunkReference]
    model: str
    tokens_used: int

# RAG Pipeline Models
@dataclass
class RAGResponse:
    query_id: str
    answer: str
    source_chunks: List[ChunkReference]
    relevance_scores: List[float]
    processing_time: float
    model: str

# Evaluation Models
@dataclass
class EvaluationDataset:
    queries: List[str]
    ground_truth: Dict[str, List[str]]
    relevance_scores: Dict[str, Dict[str, float]]

@dataclass
class EvaluationReport:
    dataset_size: int
    metrics_by_k: Dict[int, Dict[str, Dict[str, float]]]
    per_query_results: List[Dict]
    timestamp: datetime
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: UTF-8 Encoding Preservation

*For any* Vietnamese text document, extracting and loading the document should preserve UTF-8 character encoding without corruption.

**Validates: Requirements 1.2**

### Property 2: Document Metadata Completeness

*For any* loaded document, all required metadata fields (filename, upload timestamp, file size) must be populated and accessible.

**Validates: Requirements 1.4**

### Property 3: Unicode Normalization Idempotence

*For any* Vietnamese text, applying NFC normalization twice should produce the same result as applying it once: `normalize(normalize(x)) == normalize(x)`.

**Validates: Requirements 2.1**

### Property 4: Whitespace Cleaning Invariant

*For any* text, after cleaning, the output should contain no consecutive spaces except at paragraph boundaries (double newlines).

**Validates: Requirements 2.2**

### Property 5: Diacritics Preservation

*For any* Vietnamese text containing diacritical marks, the cleaning process should preserve all diacritics without modification or removal.

**Validates: Requirements 2.3**

### Property 6: Control Character Filtering

*For any* text, after cleaning, the output should contain no control characters except newline (`\n`) and tab (`\t`).

**Validates: Requirements 2.4**

### Property 7: Lowercase Conversion Completeness

*For any* text, after cleaning, all characters in the output should be lowercase (no uppercase characters should remain).

**Validates: Requirements 2.5**

### Property 8: Chunk Size Bounds

*For any* input text, all generated chunks must have a character length within the range [200, 1000] characters.

**Validates: Requirements 3.5**

### Property 9: Chunk Metadata Completeness

*For any* generated chunk, all required metadata fields (document_id, chunk_index, heading_context) must be present and non-null where applicable.

**Validates: Requirements 3.6**

### Property 10: Embedding Dimensionality

*For any* text chunk, the generated embedding must be exactly 768 dimensions.

**Validates: Requirements 4.2**

### Property 11: Embedding Batch Consistency

*For any* list of text chunks, processing them in batches should produce the same embeddings as processing them sequentially.

**Validates: Requirements 4.3**

### Property 12: Embedding Normalization

*For any* generated embedding vector, its L2 norm must equal 1.0 (unit length).

**Validates: Requirements 4.5**

### Property 13: Vector Store Round-Trip

*For any* embedding with associated text and metadata, storing it in the vector store and then retrieving it should return the same data without loss.

**Validates: Requirements 5.1**

### Property 14: Similarity Score Ordering

*For any* retrieval result, the returned chunks must be sorted in descending order by similarity score (each score >= next score).

**Validates: Requirements 5.2, 8.4**

### Property 15: Document Deletion Completeness

*For any* document, after deletion, querying the vector store should return zero chunks associated with that document's ID.

**Validates: Requirements 5.6**

### Property 16: Ingestion Status Validity

*For any* document at any point in time, its ingestion status must be one of the four valid values: {pending, processing, completed, failed}.

**Validates: Requirements 6.5**

### Property 17: Query Length Validation

*For any* query string, validation should accept it if and only if its length is within the range [10, 500] characters.

**Validates: Requirements 7.2**

### Property 18: Retrieval K Bounds

*For any* K value, the retriever should accept it if and only if K is an integer in the range [1, 20].

**Validates: Requirements 8.3, 16.4**

### Property 19: Retrieval Result Count

*For any* query vector and K value, the retriever should return exactly K results, or fewer if insufficient chunks exist in the vector store.

**Validates: Requirements 8.1**

### Property 20: Similarity Score Presence

*For any* retrieved chunk, it must include a non-null similarity score.

**Validates: Requirements 8.5**

### Property 21: Prompt Completeness

*For any* query and retrieved context chunks, the constructed prompt must contain both the query text and all chunk texts.

**Validates: Requirements 9.2, 9.3**

### Property 22: Vietnamese Response Instruction

*For any* generated prompt, it must include instructions for the LLM to respond in Vietnamese.

**Validates: Requirements 9.4**

### Property 23: Answer Token Limit

*For any* generated answer, the token count must not exceed 500 tokens.

**Validates: Requirements 9.6**

### Property 24: Answer Completeness

*For any* completed generation, the response must contain both answer text and source chunk references.

**Validates: Requirements 9.7**

### Property 25: Query Logging Completeness

*For any* processed query, the log entry must contain timestamp, retrieved chunks, and generated answer.

**Validates: Requirements 10.4**

### Property 26: RAG Response Completeness

*For any* completed query, the response must contain answer text, source chunks, and relevance scores.

**Validates: Requirements 10.5**

### Property 27: Precision@K Bounds

*For any* retrieval result and ground truth, the computed Precision@K value must be in the range [0, 1].

**Validates: Requirements 11.1**

### Property 28: Recall@K Bounds

*For any* retrieval result and ground truth, the computed Recall@K value must be in the range [0, 1].

**Validates: Requirements 11.2**

### Property 29: MRR Bounds

*For any* retrieval result and ground truth, the computed Mean Reciprocal Rank (MRR) value must be in the range [0, 1].

**Validates: Requirements 11.3**

### Property 30: NDCG Bounds

*For any* retrieval result and ground truth with relevance scores, the computed NDCG value must be in the range [0, 1].

**Validates: Requirements 11.4**

### Property 31: Evaluation K Coverage

*For any* evaluation run, metrics must be computed for all four specified K values: {1, 3, 5, 10}.

**Validates: Requirements 11.5**

### Property 32: Evaluation Query Coverage

*For any* evaluation dataset with N queries, exactly N retrieval operations must be performed during evaluation.

**Validates: Requirements 12.2**

### Property 33: Evaluation Report Completeness

*For any* completed evaluation, the report must contain all computed metrics (Precision@K, Recall@K, MRR, NDCG) for all K values.

**Validates: Requirements 12.5**

### Property 34: JSON Export Round-Trip

*For any* evaluation result, exporting to JSON and then parsing should preserve all data without loss.

**Validates: Requirements 12.6**

### Property 35: Job ID Assignment

*For any* uploaded document, an ingestion job ID must be returned immediately upon successful upload.

**Validates: Requirements 13.4**

### Property 36: Query Response Structure

*For any* submitted query, the JSON response must contain answer, source chunks, and relevance scores.

**Validates: Requirements 13.5**

### Property 37: Configuration Parameter Acceptance

*For any* valid configuration parameter value (API key, model path, chunk size, K value, connection params), the system should accept it during configuration loading.

**Validates: Requirements 14.2, 14.3, 14.4, 14.5, 14.6**

### Property 38: Error Log Completeness

*For any* error that occurs in any component, the log entry must contain timestamp, component name, and error details.

**Validates: Requirements 15.1**

### Property 39: Log Severity Validity

*For any* log entry, the severity level must be one of the four valid values: {DEBUG, INFO, WARNING, ERROR}.

**Validates: Requirements 15.2**

### Property 40: Performance Metrics Logging

*For any* ingestion or query operation, performance metrics (including processing time) must be logged.

**Validates: Requirements 15.4**

### Property 41: API Request Logging

*For any* API request, the log entry must contain endpoint, parameters, and response status.

**Validates: Requirements 15.5**

### Property 42: Sensitive Data Redaction

*For any* log entry containing API keys or sensitive tokens, those values must be redacted in the logged output.

**Validates: Requirements 15.6**

### Property 43: File Size Validation

*For any* file upload, validation should accept it if and only if the file size does not exceed 50 MB.

**Validates: Requirements 16.1**

### Property 44: File Extension Validation

*For any* file upload, validation should accept it if and only if the file extension is in {.pdf, .docx, .txt}.

**Validates: Requirements 16.2**

### Property 45: UTF-8 Query Validation

*For any* query string, validation should verify that it contains valid UTF-8 encoded characters and reject invalid encodings.

**Validates: Requirements 16.3**

### Property 46: Validation Error Messages

*For any* validation failure, the error response must include a descriptive message identifying the specific validation rule that failed.

**Validates: Requirements 16.5**

### Property 47: Path Sanitization

*For any* file path input containing directory traversal attempts (e.g., "../"), sanitization must prevent access outside the allowed directory.

**Validates: Requirements 16.6**

## Testing Strategy

### Unit Tests

Unit tests will focus on individual components with specific examples and edge cases:

**Document Loader**
- Test loading of valid PDF, DOCX, TXT files
- Test error handling for corrupted files
- Test metadata extraction accuracy

**Text Cleaner**
- Test NFC normalization with Vietnamese characters
- Test whitespace handling edge cases
- Test diacritics preservation with various tone marks
- Test control character removal

**Semantic Chunker**
- Test paragraph-based chunking
- Test handling of oversized paragraphs and sentences
- Test heading detection with various patterns
- Test chunk size enforcement at boundaries

**Embedding Service**
- Test model loading and initialization
- Test embedding generation for sample texts
- Test batch processing logic
- Test error handling for invalid inputs

**Vector Store**
- Test CRUD operations (create, read, delete)
- Test similarity search with known examples
- Test incremental indexing

**Retriever**
- Test K parameter validation
- Test result sorting
- Test empty result handling

**LLM Service**
- Test prompt construction with sample chunks
- Test Vietnamese instruction inclusion
- Test token limit enforcement
- Test error handling for API failures

**Evaluation Framework**
- Test metric calculations with known datasets
- Test edge cases (empty results, perfect ranking)
- Test JSON export and parsing

### Property-Based Tests

Property tests will verify universal properties across randomized inputs. Each property test will run a minimum of 100 iterations and reference its corresponding design property.

**Test Configuration**
```python
from hypothesis import given, settings, strategies as st
import pytest

# Configure hypothesis for 100 iterations minimum
settings.register_profile("default", max_examples=100, deadline=None)
settings.load_profile("default")
```

**Example Property Test Structure**
```python
@given(text=st.text(min_size=10, max_size=5000))
@settings(max_examples=100)
def test_property_3_unicode_normalization_idempotence(text):
    """
    Property 3: Unicode Normalization Idempotence
    Feature: rag-llm-core, Property 3: For any Vietnamese text, 
    applying NFC normalization twice should produce the same result 
    as applying it once.
    """
    cleaner = TextCleaner()
    
    # Apply normalization once
    normalized_once = unicodedata.normalize('NFC', text)
    
    # Apply normalization twice
    normalized_twice = unicodedata.normalize('NFC', normalized_once)
    
    # They should be equal
    assert normalized_once == normalized_twice
```

**Property Test Categories**

1. **Text Processing Properties** (Properties 3-7)
   - Unicode normalization idempotence
   - Whitespace cleaning invariants
   - Diacritics preservation
   - Control character filtering
   - Lowercase conversion

2. **Chunking Properties** (Properties 8-9)
   - Chunk size bounds enforcement
   - Metadata completeness

3. **Embedding Properties** (Properties 10-12)
   - Dimensionality consistency
   - Batch processing consistency
   - Vector normalization

4. **Vector Store Properties** (Properties 13-15)
   - Storage round-trip preservation
   - Similarity score ordering
   - Deletion completeness

5. **Retrieval Properties** (Properties 17-20)
   - Query validation bounds
   - K parameter validation
   - Result count correctness
   - Score presence

6. **Generation Properties** (Properties 21-24)
   - Prompt completeness
   - Vietnamese instruction presence
   - Token limit enforcement
   - Response completeness

7. **Evaluation Properties** (Properties 27-34)
   - Metric bound checking
   - Coverage guarantees
   - Report completeness
   - JSON serialization round-trip

8. **Validation Properties** (Properties 43-47)
   - File size validation
   - Extension validation
   - UTF-8 validation
   - Error message presence
   - Path sanitization

**Generator Strategies**

```python
# Vietnamese text generator
vietnamese_chars = "aăâbcdđeêghiklmnoôơpqrstuưvxy" + "àáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
vietnamese_text = st.text(alphabet=vietnamese_chars, min_size=1, max_size=1000)

# Chunk size text
chunk_text = st.text(min_size=200, max_size=1000)

# Query text
query_text = st.text(min_size=10, max_size=500)

# K values
k_values = st.integers(min_value=1, max_value=20)

# File sizes
file_sizes = st.integers(min_value=0, max_value=100*1024*1024)

# Embeddings (768-dim)
embeddings = st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=768, max_size=768)
```

### Integration Tests

Integration tests will verify end-to-end workflows:

1. **Complete Ingestion Pipeline**
   - Upload document → verify chunks created → verify embeddings stored
   
2. **Complete RAG Pipeline**
   - Submit query → verify retrieval → verify answer generation
   
3. **Status Tracking**
   - Upload document → poll status → verify completion

4. **Health Checks**
   - Verify all components report healthy status

5. **Concurrent Ingestion**
   - Upload multiple documents simultaneously → verify all complete

## Dependencies

### Python Packages

```txt
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Document Processing
pypdf2==3.0.1
python-docx==1.1.0
python-magic==0.4.27

# Embedding and ML
transformers==4.35.2
torch==2.1.1
sentencepiece==0.1.99

# Vector Store
chromadb==0.4.18

# LLM
openai==1.3.7

# Utilities
numpy==1.26.2
tenacity==8.2.3
python-multipart==0.0.6

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
hypothesis==6.92.0

# Logging
structlog==23.2.0
```

### External Services

- **OpenAI API**: GPT-3.5-turbo or GPT-4 for answer generation
- **VietAI Model**: vit5-base-vietnamese-embedding (can be downloaded from Hugging Face)

### System Requirements

- Python 3.9+
- 8GB RAM minimum (16GB recommended for model loading)
- 10GB disk space for models and vector store
- GPU optional but recommended for faster embedding generation

## Deployment Considerations

### Startup Sequence

```python
async def startup_event():
    """Initialize system on startup."""
    
    logger.info("Starting RAG LLM Core System")
    
    # 1. Validate configuration
    validate_configuration(settings)
    
    # 2. Load embedding model
    logger.info("Loading VietAI embedding model...")
    embedding_service = EmbeddingService(settings.vietai_model_path)
    
    # 3. Initialize vector store
    logger.info("Connecting to ChromaDB...")
    vector_store = VectorStore(collection_name=settings.chroma_collection)
    
    # 4. Initialize LLM service
    logger.info("Initializing OpenAI client...")
    llm_service = LLMService(
        api_key=settings.openai_api_key,
        model=settings.openai_model
    )
    
    # 5. Initialize pipelines
    logger.info("Initializing pipelines...")
    global ingestion_pipeline, rag_pipeline
    ingestion_pipeline = DocumentIngestionPipeline(
        loader=DocumentLoader(),
        cleaner=TextCleaner(),
        chunker=SemanticChunker(
            min_size=settings.chunk_min_size,
            max_size=settings.chunk_max_size
        ),
        embedding_service=embedding_service,
        vector_store=vector_store
    )
    rag_pipeline = RAGPipeline(
        retriever=Retriever(vector_store, embedding_service),
        llm_service=llm_service
    )
    
    logger.info("System startup complete")

app.add_event_handler("startup", startup_event)
```

### Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=sk-...

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or with reload for development
uvicorn app.main:app --reload
```

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-XX  
**Author**: AI System Designer
