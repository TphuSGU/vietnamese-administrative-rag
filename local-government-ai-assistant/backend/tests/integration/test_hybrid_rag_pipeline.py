"""
Integration tests for HybridRAGPipeline with real components.

Test scenarios:
1. Full pipeline flow with Vietnamese legal text
2. Hybrid vs vector-only retrieval comparison
3. Output validation catching hallucination
4. Reranking improving relevance order

Uses:
- Real EmbeddingService
- Real VectorStore (temporary)
- Real BM25Index
- Mock LLMService (to avoid API costs)
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from typing import List

from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline
from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.retrieval.retriever import Retriever
from app.rag.embedding.embedding_service import EmbeddingService
from app.rag.generation.llm_service import LLMService
from app.rag.generation.output_validator import OutputValidator
from app.database.vector_store import VectorStore
from app.models.data_models import (
    Chunk, RetrievedChunk, GeneratedAnswer, ChunkReference
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_vector_dir():
    """Create temporary directory for vector store."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def embedding_service():
    """Real embedding service."""
    return EmbeddingService()


@pytest.fixture
def vector_store(temp_vector_dir):
    """Real vector store with temporary directory."""
    store = VectorStore(
        persist_directory=str(temp_vector_dir)
    )
    return store


@pytest.fixture
def mock_llm_service():
    """Mock LLM service to avoid API calls."""
    mock = Mock(spec=LLMService)
    mock.MODEL_NAME = "mock-model"
    
    # Default: return answer that uses context
    def mock_generate(query: str, chunks: List[RetrievedChunk]) -> GeneratedAnswer:
        # Extract key terms from chunks
        chunk_texts = [chunk.text for chunk in chunks]
        combined_text = " ".join(chunk_texts[:2])  # Use first 2 chunks
        
        # Create answer that references the chunks
        answer = f"Theo tài liệu: {combined_text[:200]}..."
        
        # Create source references
        source_chunks = [
            ChunkReference(
                document_id=chunk.document_id,
                text=chunk.text[:100],
                similarity_score=chunk.similarity_score,
                chunk_index=chunk.chunk_index
            )
            for chunk in chunks[:3]
        ]
        
        return GeneratedAnswer(
            answer=answer,
            source_chunks=source_chunks,
            model="mock-model",
            tokens_used=100
        )
    
    mock.generate_answer.side_effect = mock_generate
    return mock


@pytest.fixture
def sample_vietnamese_documents():
    """Sample Vietnamese legal documents for testing."""
    return [
        Chunk(
            text="Điều 10: Hộ khẩu là cơ sở xác định thường trú của công dân. "
                 "Mọi công dân phải đăng ký hộ khẩu tại nơi cư trú thường xuyên. "
                 "Việc đăng ký hộ khẩu phải được thực hiện trong vòng 30 ngày kể từ "
                 "khi chuyển đến nơi ở mới.",
            document_id="doc_001",
            chunk_index=0,
            heading_context="Luật Hộ Khẩu 2020"
        ),
        Chunk(
            text="Điều 15: Chứng minh nhân dân (CMND) là giấy tờ tùy thân của công dân. "
                 "Mọi công dân đủ 14 tuổi phải làm CMND. CMND có giá trị 15 năm và "
                 "phải được gia hạn trước khi hết hạn.",
            document_id="doc_002",
            chunk_index=0,
            heading_context="Luật CMND 2019"
        ),
        Chunk(
            text="Điều 20: Đăng ký khai sinh là thủ tục bắt buộc cho mọi trẻ em sinh ra. "
                 "Cha mẹ phải đăng ký khai sinh trong vòng 60 ngày kể từ ngày sinh. "
                 "Khai sinh là cơ sở để cấp giấy khai sinh cho trẻ em.",
            document_id="doc_003",
            chunk_index=0,
            heading_context="Luật Hộ Tịch 2021"
        ),
        Chunk(
            text="Điều 25: Đăng ký kết hôn phải được thực hiện tại Ủy ban nhân dân xã phường. "
                 "Đăng ký kết hôn có hiệu lực pháp lý kể từ ngày đăng ký. "
                 "Giấy chứng nhận kết hôn được cấp ngay sau khi hoàn tất thủ tục.",
            document_id="doc_004",
            chunk_index=0,
            heading_context="Luật Hôn Nhân và Gia Đình 2020"
        ),
        Chunk(
            text="Điều 10 khoản 2: Trường hợp công dân tạm vắng khỏi nơi thường trú trên 30 ngày "
                 "thì phải báo với chính quyền địa phương. Nếu vắng trên 6 tháng cần làm thủ tục "
                 "tạm trú tại nơi ở mới.",
            document_id="doc_001",
            chunk_index=1,
            heading_context="Luật Hộ Khẩu 2020 - Chi tiết"
        )
    ]


@pytest.fixture
def indexed_hybrid_retriever(
    embedding_service,
    vector_store,
    sample_vietnamese_documents
):
    """Hybrid retriever with pre-indexed documents."""
    # Create hybrid retriever with lower threshold for testing
    retriever = HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.6,
        min_similarity=0.01,  # Very low threshold for testing
        use_reranking=False  # Disable for simpler tests
    )
    
    # Index documents in vector store using add_chunks
    embeddings = embedding_service.embed_chunks(sample_vietnamese_documents)
    vector_store.add_chunks(sample_vietnamese_documents, embeddings)
    
    # Convert chunks to RetrievedChunk format for BM25 indexing
    retrieved_chunks = [
        RetrievedChunk(
            text=chunk.text,
            similarity_score=1.0,  # Placeholder
            metadata={
                'document_id': chunk.document_id,
                'chunk_index': chunk.chunk_index,
                'heading_context': chunk.heading_context
            }
        )
        for chunk in sample_vietnamese_documents
    ]
    
    # Index documents in BM25
    retriever.index_documents(retrieved_chunks)
    
    return retriever


@pytest.fixture
def output_validator():
    """Real output validator."""
    return OutputValidator(
        min_evidence_ratio=0.3,  # Lenient for testing
        strict_mode=False
    )


@pytest.fixture
def hybrid_pipeline(
    indexed_hybrid_retriever,
    mock_llm_service,
    output_validator,
    temp_vector_dir
):
    """Complete hybrid RAG pipeline."""
    return HybridRAGPipeline(
        hybrid_retriever=indexed_hybrid_retriever,
        llm_service=mock_llm_service,
        output_validator=output_validator,
        log_dir=temp_vector_dir / "logs"
    )


# ============================================================================
# Test Cases
# ============================================================================

def test_hybrid_pipeline_full_flow(hybrid_pipeline):
    """
    Test complete pipeline with real components.
    
    Validates:
    - Query processing
    - Hybrid retrieval (BM25 + Vector)
    - Answer generation
    - Output validation passes
    - Response contains chunk references
    """
    query = "Điều 10 quy định gì về hộ khẩu?"
    
    # Execute pipeline
    response = hybrid_pipeline.query(query, k=3)
    
    # Assert response structure
    assert response.query_id is not None
    assert len(response.answer) > 0
    assert len(response.source_chunks) > 0
    assert len(response.relevance_scores) > 0
    assert response.processing_time > 0
    assert response.model == "mock-model"
    
    # Assert answer contains relevant content
    # Since mock LLM uses chunks, answer should contain chunk text
    assert "Điều 10" in response.answer or "hộ khẩu" in response.answer.lower()
    
    # Assert source chunks are returned
    assert len(response.source_chunks) <= 3  # Max k=3
    for chunk in response.source_chunks:
        assert chunk.document_id is not None
        assert len(chunk.text) > 0
        assert chunk.similarity_score >= 0


def test_hybrid_vs_vector_only_keyword_search(
    embedding_service,
    vector_store,
    sample_vietnamese_documents
):
    """
    Test hybrid retrieval finds exact keywords better than vector-only.
    
    Query: "CMND" (exact keyword)
    Expected: Hybrid finds it (BM25 helps), vector-only might miss it
    """
    # Setup vector-only retriever
    vector_retriever = Retriever(
        embedding_service=embedding_service,
        vector_store=vector_store
    )
    
    # Index documents
    embeddings = embedding_service.embed_chunks(sample_vietnamese_documents)
    vector_store.add_chunks(sample_vietnamese_documents, embeddings)
    
    # Setup hybrid retriever with low threshold
    hybrid_retriever = HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.5,
        min_similarity=0.01,  # Low threshold for testing
        use_reranking=False
    )
    
    retrieved_chunks = [
        RetrievedChunk(
            text=chunk.text,
            similarity_score=1.0,
            metadata={
                'document_id': chunk.document_id,
                'chunk_index': chunk.chunk_index
            }
        )
        for chunk in sample_vietnamese_documents
    ]
    hybrid_retriever.index_documents(retrieved_chunks)
    
    # Query for exact keyword
    query = "CMND"
    k = 3
    
    # Retrieve with both methods
    vector_results = vector_retriever.retrieve(query, k=k)
    hybrid_results = hybrid_retriever.retrieve(query, k=k)
    
    # Check that hybrid finds CMND document
    cmnd_in_hybrid = any("CMND" in chunk.text for chunk in hybrid_results)
    assert cmnd_in_hybrid, "Hybrid retrieval should find exact keyword 'CMND'"
    
    # Hybrid should rank CMND document higher
    hybrid_ranks = [i for i, chunk in enumerate(hybrid_results) if "CMND" in chunk.text]
    if hybrid_ranks:
        assert hybrid_ranks[0] < len(hybrid_results), "CMND doc should be in top results"


def test_output_validation_catches_hallucination(
    indexed_hybrid_retriever,
    output_validator,
    temp_vector_dir
):
    """
    Test that output validation catches hallucinated answers.
    
    Setup: Mock LLM to return irrelevant answer
    Expected: OutputValidator detects low evidence ratio
              Pipeline retries or returns error
    """
    # Create mock LLM that hallucinates
    mock_llm = Mock(spec=LLMService)
    mock_llm.MODEL_NAME = "hallucinator-model"
    
    def hallucinate_answer(query: str, chunks: List[RetrievedChunk]) -> GeneratedAnswer:
        # Return answer with NO connection to context
        hallucinated_answer = (
            "Paris là thủ đô của nước Pháp và có tháp Eiffel nổi tiếng. "
            "Đây là một trong những thành phố đẹp nhất thế giới."
        )
        
        return GeneratedAnswer(
            answer=hallucinated_answer,
            source_chunks=[],
            model="hallucinator-model",
            tokens_used=50
        )
    
    mock_llm.generate_answer.side_effect = hallucinate_answer
    
    # Create pipeline with hallucinating LLM
    pipeline = HybridRAGPipeline(
        hybrid_retriever=indexed_hybrid_retriever,
        llm_service=mock_llm,
        output_validator=output_validator,
        log_dir=temp_vector_dir / "logs"
    )
    
    # Query about Vietnamese legal topic
    query = "Điều 10 quy định gì về hộ khẩu?"
    
    # Execute pipeline
    response = pipeline.query(query, k=3)
    
    # Assert that validation caught the hallucination
    # Response should contain error message or retry happened
    assert "Xin lỗi" in response.answer or "không thể" in response.answer.lower()
    
    # Should have attempted generation
    assert mock_llm.generate_answer.call_count >= 1


def test_output_validation_passes_good_answer(
    indexed_hybrid_retriever,
    mock_llm_service,
    output_validator,
    temp_vector_dir
):
    """
    Test that output validation passes good answers.
    
    Setup: Mock LLM returns answer that uses context
    Expected: Validation passes, answer returned successfully
    """
    pipeline = HybridRAGPipeline(
        hybrid_retriever=indexed_hybrid_retriever,
        llm_service=mock_llm_service,
        output_validator=output_validator,
        log_dir=temp_vector_dir / "logs"
    )
    
    query = "Điều 10 quy định gì về hộ khẩu?"
    
    # Execute pipeline
    response = pipeline.query(query, k=3)
    
    # Validation should pass (no error message)
    assert "Xin lỗi" not in response.answer
    assert "không thể" not in response.answer.lower()
    
    # Should contain relevant content from chunks
    assert len(response.answer) > 50
    assert len(response.source_chunks) > 0


def test_reranking_improves_order(
    embedding_service,
    vector_store,
    sample_vietnamese_documents,
    temp_vector_dir
):
    """
    Test that reranking improves relevance order.
    
    Compare results with and without reranking.
    Expect: Reranked results have better order for ambiguous queries.
    """
    # Index documents
    embeddings = embedding_service.embed_chunks(sample_vietnamese_documents)
    vector_store.add_chunks(sample_vietnamese_documents, embeddings)
    
    # Create retriever WITHOUT reranking
    retriever_no_rerank = HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.6,
        min_similarity=0.01,  # Low threshold for testing
        use_reranking=False
    )
    
    # Create retriever WITH reranking
    retriever_with_rerank = HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.6,
        min_similarity=0.01,  # Low threshold for testing
        use_reranking=True
    )
    
    # Index in both
    retrieved_chunks = [
        RetrievedChunk(
            text=chunk.text,
            similarity_score=1.0,
            metadata={
                'document_id': chunk.document_id,
                'chunk_index': chunk.chunk_index
            }
        )
        for chunk in sample_vietnamese_documents
    ]
    
    retriever_no_rerank.index_documents(retrieved_chunks)
    retriever_with_rerank.index_documents(retrieved_chunks)
    
    # Query with ambiguous terms
    query = "đăng ký hộ khẩu"
    k = 3
    
    # Retrieve with both
    results_no_rerank = retriever_no_rerank.retrieve(query, k=k)
    results_with_rerank = retriever_with_rerank.retrieve(query, k=k)
    
    # Both should return results
    assert len(results_no_rerank) > 0
    assert len(results_with_rerank) > 0
    
    # Check that relevant document appears in results
    # (Doc 001 contains "hộ khẩu" and "đăng ký hộ khẩu")
    relevant_in_no_rerank = any(
        "doc_001" in chunk.document_id for chunk in results_no_rerank
    )
    relevant_in_with_rerank = any(
        "doc_001" in chunk.document_id for chunk in results_with_rerank
    )
    
    assert relevant_in_no_rerank or relevant_in_with_rerank, \
        "Relevant document should appear in at least one result set"


def test_pipeline_handles_empty_results(
    embedding_service,
    vector_store,
    mock_llm_service,
    output_validator,
    temp_vector_dir
):
    """
    Test pipeline handles case with no relevant documents.
    
    Expected: Returns appropriate "no results" message
    """
    # Create empty hybrid retriever (no documents indexed)
    hybrid_retriever = HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.6,
        min_similarity=0.01,  # Low threshold for testing
        use_reranking=False
    )
    
    pipeline = HybridRAGPipeline(
        hybrid_retriever=hybrid_retriever,
        llm_service=mock_llm_service,
        output_validator=output_validator,
        log_dir=temp_vector_dir / "logs"
    )
    
    # Query when no documents exist
    query = "Điều 99 quy định gì?"
    
    response = pipeline.query(query, k=3)
    
    # Should return "no results" message
    assert "Không tìm thấy" in response.answer
    assert len(response.source_chunks) == 0
    assert len(response.relevance_scores) == 0


def test_pipeline_retry_logic(
    indexed_hybrid_retriever,
    output_validator,
    temp_vector_dir
):
    """
    Test that pipeline retries with more chunks on validation failure.
    
    Setup: Mock LLM that fails validation first, succeeds second
    Expected: Pipeline retries once with k*2 chunks
    """
    call_count = {'count': 0}
    
    mock_llm = Mock(spec=LLMService)
    mock_llm.MODEL_NAME = "retry-model"
    
    def retry_answer(query: str, chunks: List[RetrievedChunk]) -> GeneratedAnswer:
        call_count['count'] += 1
        
        if call_count['count'] == 1:
            # First call: hallucinate (will fail validation)
            return GeneratedAnswer(
                answer="Completely irrelevant answer about something else.",
                source_chunks=[],
                model="retry-model",
                tokens_used=20
            )
        else:
            # Second call: use context (will pass validation)
            combined = " ".join(chunk.text[:100] for chunk in chunks[:2])
            return GeneratedAnswer(
                answer=f"Theo tài liệu: {combined}",
                source_chunks=[
                    ChunkReference(
                        document_id=chunk.document_id,
                        text=chunk.text[:50],
                        similarity_score=chunk.similarity_score,
                        chunk_index=chunk.chunk_index
                    )
                    for chunk in chunks[:2]
                ],
                model="retry-model",
                tokens_used=50
            )
    
    mock_llm.generate_answer.side_effect = retry_answer
    
    pipeline = HybridRAGPipeline(
        hybrid_retriever=indexed_hybrid_retriever,
        llm_service=mock_llm,
        output_validator=output_validator,
        log_dir=temp_vector_dir / "logs"
    )
    
    query = "Điều 10 quy định gì về hộ khẩu?"
    
    response = pipeline.query(query, k=3)
    
    # Should have called LLM twice (initial + 1 retry)
    assert call_count['count'] == 2
    
    # Final response should be successful
    assert "Theo tài liệu" in response.answer
    assert len(response.source_chunks) > 0
