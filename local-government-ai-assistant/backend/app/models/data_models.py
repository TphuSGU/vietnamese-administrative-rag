"""
Core data models for RAG LLM System.

Defines dataclasses for documents, chunks, search results, and pipeline responses.
Implements requirements from design document for data structure completeness.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Document Models
# ============================================================================

@dataclass
class Document:
    """
    Loaded document with metadata.
    
    Validates: Requirements 1.4
    """
    id: str
    text: str
    filename: str
    file_size: int
    upload_timestamp: datetime
    format: str  # 'pdf', 'docx', 'txt'
    
    def __post_init__(self):
        """Validate required fields are present."""
        if not self.id:
            raise ValueError("Document ID is required")
        if not self.filename:
            raise ValueError("Document filename is required")


# ============================================================================
# Chunk Models
# ============================================================================

@dataclass
class Chunk:
    """
    Text chunk with metadata.
    
    Validates: Requirements 3.6
    """
    text: str
    document_id: str
    chunk_index: int
    heading_context: Optional[str] = None
    char_start: int = 0
    char_end: int = 0
    
    def __post_init__(self):
        """Validate chunk metadata completeness."""
        if not self.text:
            raise ValueError("Chunk text cannot be empty")
        if not self.document_id:
            raise ValueError("Chunk document_id is required")
        if self.chunk_index < 0:
            raise ValueError("Chunk index must be non-negative")
    
    @property
    def length(self) -> int:
        """Get chunk text length."""
        return len(self.text)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for storage."""
        return {
            "text": self.text,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "heading_context": self.heading_context,
            "char_start": self.char_start,
            "char_end": self.char_end
        }


# ============================================================================
# Ingestion Models
# ============================================================================

class IngestionStatus(Enum):
    """
    Status values for document ingestion pipeline.
    
    Validates: Requirements 6.5
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IngestionResult:
    """
    Result of document ingestion operation.
    
    Validates: Requirements 6.3
    """
    job_id: str
    status: IngestionStatus
    chunk_count: int
    document_id: str
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    
    def is_successful(self) -> bool:
        """Check if ingestion completed successfully."""
        return self.status == IngestionStatus.COMPLETED


# ============================================================================
# Retrieval Models
# ============================================================================

@dataclass
class SearchResult:
    """
    Vector store search result.
    
    Validates: Requirements 5.1, 8.4
    """
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    similarity_score: float
    distance: float
    
    def __post_init__(self):
        """Validate search result completeness."""
        if self.similarity_score is None:
            raise ValueError("Similarity score is required")
    
    @property
    def chunk_text(self) -> str:
        """Backward compatibility alias."""
        return self.text


@dataclass
class RetrievedChunk:
    """
    Retrieved chunk from vector store with metadata.
    
    Validates: Requirements 8.5, 8.6
    """
    text: str
    similarity_score: float
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate retrieved chunk has required fields."""
        if self.similarity_score is None:
            raise ValueError("Similarity score is required")
        if not isinstance(self.metadata, dict):
            raise ValueError("Metadata must be a dictionary")
    
    @property
    def document_id(self) -> str:
        """Extract document ID from metadata."""
        return self.metadata.get('document_id', '')
    
    @property
    def heading_context(self) -> Optional[str]:
        """Extract heading context from metadata."""
        return self.metadata.get('heading_context')
    
    @property
    def chunk_index(self) -> int:
        """Extract chunk index from metadata."""
        return self.metadata.get('chunk_index', -1)


# ============================================================================
# Generation Models
# ============================================================================

@dataclass
class ChunkReference:
    """
    Reference to a source chunk in generated answer.
    
    Validates: Requirements 9.7
    """
    document_id: str
    text: str  # Preview text
    similarity_score: float
    chunk_index: Optional[int] = None


@dataclass
class GeneratedAnswer:
    """
    Answer generated by LLM with source references.
    
    Validates: Requirements 9.7
    """
    answer: str
    source_chunks: List[ChunkReference]
    model: str
    tokens_used: int
    
    def __post_init__(self):
        """Validate generated answer completeness."""
        if not self.answer:
            raise ValueError("Answer text is required")
        if not isinstance(self.source_chunks, list):
            raise ValueError("Source chunks must be a list")


# ============================================================================
# RAG Pipeline Models
# ============================================================================

@dataclass
class RAGResponse:
    """
    Complete response from RAG pipeline.
    
    Validates: Requirements 10.5
    """
    query_id: str
    answer: str
    source_chunks: List[ChunkReference]
    relevance_scores: List[float]
    processing_time: float
    model: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Validate RAG response completeness."""
        if not self.query_id:
            raise ValueError("Query ID is required")
        if not self.answer:
            raise ValueError("Answer is required")
        if not isinstance(self.source_chunks, list):
            raise ValueError("Source chunks must be a list")
        if not isinstance(self.relevance_scores, list):
            raise ValueError("Relevance scores must be a list")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary for API serialization."""
        return {
            "query_id": self.query_id,
            "answer": self.answer,
            "source_chunks": [
                {
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "similarity_score": chunk.similarity_score,
                    "chunk_index": chunk.chunk_index
                }
                for chunk in self.source_chunks
            ],
            "relevance_scores": self.relevance_scores,
            "processing_time": self.processing_time,
            "model": self.model,
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================================
# Evaluation Models
# ============================================================================

@dataclass
class EvaluationDataset:
    """
    Dataset for retrieval evaluation.
    
    Validates: Requirements 11.6
    """
    queries: List[str]
    ground_truth: Dict[str, List[str]]  # query -> list of relevant doc IDs
    relevance_scores: Dict[str, Dict[str, float]]  # query -> doc_id -> score [0-3]
    
    def __post_init__(self):
        """Validate dataset completeness."""
        if not self.queries:
            raise ValueError("Queries list cannot be empty")
        if not self.ground_truth:
            raise ValueError("Ground truth mapping is required")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvaluationDataset':
        """Create dataset from dictionary."""
        return cls(
            queries=data['queries'],
            ground_truth=data['ground_truth'],
            relevance_scores=data.get('relevance_scores', {})
        )
    
    def validate(self) -> None:
        """Validate dataset consistency."""
        for query in self.queries:
            if query not in self.ground_truth:
                raise ValueError(f"Query '{query}' missing from ground_truth")


@dataclass
class EvaluationReport:
    """
    Evaluation results report.
    
    Validates: Requirements 12.5
    """
    dataset_size: int
    metrics_by_k: Dict[int, Dict[str, Dict[str, float]]]
    per_query_results: List[Dict[str, Any]]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON export."""
        return {
            "dataset_size": self.dataset_size,
            "metrics_by_k": self.metrics_by_k,
            "per_query_results": self.per_query_results,
            "timestamp": self.timestamp.isoformat()
        }
    
    def print_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Evaluation Report ({self.dataset_size} queries)",
            "=" * 50
        ]
        
        for k in [1, 3, 5, 10]:
            if k in self.metrics_by_k:
                metrics = self.metrics_by_k[k]
                lines.append(f"\nK = {k}")
                for metric_name in ['precision', 'recall', 'ndcg']:
                    if metric_name in metrics:
                        m = metrics[metric_name]
                        lines.append(
                            f"  {metric_name.capitalize()}@{k}: "
                            f"{m['mean']:.3f} ± {m['std']:.3f}"
                        )
        
        if 'mrr' in self.metrics_by_k:
            mrr = self.metrics_by_k['mrr']
            lines.append(f"\nMRR: {mrr['mean']:.3f} ± {mrr['std']:.3f}")
        
        return "\n".join(lines)
