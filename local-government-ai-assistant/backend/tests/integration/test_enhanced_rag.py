"""Integration test for enhanced RAG with hybrid search and validation"""

import pytest
from pathlib import Path

from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.rag.generation.llm_service import LLMService
from app.rag.generation.output_validator import OutputValidator
from app.models.data_models import RetrievedChunk

@pytest.fixture
def hybrid_retriever(tmp_path):
    """Create hybrid retriever with real components"""
    vector_store = VectorStore(persist_directory=str(tmp_path / "chroma"))
    embedding_service = EmbeddingService()

    return HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.6,
        min_similarity=0.7,
        use_reranking=True
    )

def test_hybrid_retriever_initialization(hybrid_retriever):
    """Test hybrid retriever initializes correctly"""
    assert hybrid_retriever is not None
    assert hybrid_retriever.bm25_index is not None
    assert hybrid_retriever.alpha == 0.6
    assert hybrid_retriever.min_similarity == 0.7
    assert hybrid_retriever.reranker is not None

    print("✅ Hybrid retriever initialized successfully")

def test_output_validator():
    """Test output validator initialization"""
    validator = OutputValidator(min_evidence_ratio=0.4)

    # Test valid answer
    answer = "Theo Điều 10, đăng ký hộ khẩu cần CMND và sổ hộ khẩu."
    query = "Cần giấy tờ gì?"

    # Create mock chunks
    chunks = [
        RetrievedChunk(
            text="Điều 10: Đăng ký hộ khẩu cần CMND và sổ hộ khẩu.",
            similarity_score=0.9,
            metadata={}
        )
    ]

    is_valid, error = validator.validate(answer, query, chunks)
    assert is_valid, f"Validation failed: {error}"

    print("✅ Output validator working correctly")

def test_bm25_keyword_search():
    """Test BM25 finds exact keywords"""
    from app.rag.retrieval.bm25_index import BM25Index

    # Create index
    bm25 = BM25Index()

    # Mock chunks with more text for better scoring
    chunks = [
        RetrievedChunk(
            text="Điều 10 quy định về đăng ký hộ khẩu thường trú tại địa phương",
            similarity_score=0,
            metadata={}
        ),
        RetrievedChunk(
            text="Khoản 3 hướng dẫn thủ tục cấp CMND mới cho công dân",
            similarity_score=0,
            metadata={}
        ),
        RetrievedChunk(
            text="Đăng ký kinh doanh cần chuẩn bị các giấy tờ sau",
            similarity_score=0,
            metadata={}
        ),
    ]

    bm25.index_chunks(chunks)

    # Search for keyword that definitely appears
    results = bm25.search("đăng ký hộ khẩu", k=5)

    assert len(results) > 0, f"Expected results, got empty list"
    # Check top result contains the keywords
    top_chunk_text = results[0][0].text.lower()
    assert "đăng ký" in top_chunk_text
    assert "hộ khẩu" in top_chunk_text

    print(f"✅ BM25 found {len(results)} results")
    print(f"✅ Top result: {results[0][0].text[:50]}...")
    print(f"✅ BM25 score: {results[0][1]:.3f}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
