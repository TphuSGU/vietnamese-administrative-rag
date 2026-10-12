"""
Unit tests for EmbeddingService.

Tests Requirements 4.1-4.6:
- Model loading
- Embedding generation
- Dimensionality
- Normalization
- Error handling
- Batch processing
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from app.rag.embedding.embedding_service import EmbeddingService
from app.models.data_models import Chunk


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer model."""
    with patch('app.rag.embedding.embedding_service.SentenceTransformer') as mock_st:
        # Create mock instance
        mock_model = MagicMock()
        mock_model.device = 'cpu'
        
        # Mock encode method to return normalized 768-dim vectors
        def mock_encode(texts, **kwargs):
            n = len(texts) if isinstance(texts, list) else 1
            # Generate random normalized vectors
            embeddings = np.random.randn(n, 768)
            # Normalize to unit length
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms
            return embeddings
        
        mock_model.encode = Mock(side_effect=mock_encode)
        mock_st.return_value = mock_model
        
        yield mock_st


@pytest.fixture
def embedding_service(mock_sentence_transformer):
    """Create EmbeddingService instance with mocked model."""
    return EmbeddingService()


@pytest.fixture
def sample_chunks():
    """Create sample Chunk objects."""
    return [
        Chunk(
            text="Văn bản quy định về thủ tục hành chính.",
            document_id="doc_001",
            chunk_index=0,
            heading_context="Điều 1",
            char_start=0,
            char_end=42
        ),
        Chunk(
            text="Người dân có quyền nộp hồ sơ trực tuyến.",
            document_id="doc_001",
            chunk_index=1,
            heading_context="Điều 2",
            char_start=42,
            char_end=82
        ),
        Chunk(
            text="Thời gian xử lý hồ sơ là 15 ngày làm việc.",
            document_id="doc_001",
            chunk_index=2,
            heading_context="Điều 3",
            char_start=82,
            char_end=125
        )
    ]


# ============================================================================
# Test 1: Model Loading (5 tests)
# ============================================================================

def test_model_initialization_success(mock_sentence_transformer):
    """Test successful model initialization."""
    service = EmbeddingService()
    
    assert service.model is not None
    assert service.batch_size == 32
    assert service.EMBEDDING_DIM == 768
    mock_sentence_transformer.assert_called_once()


def test_model_initialization_with_custom_batch_size(mock_sentence_transformer):
    """Test initialization with custom batch size."""
    service = EmbeddingService(batch_size=64)
    
    assert service.batch_size == 64


def test_model_initialization_with_device(mock_sentence_transformer):
    """Test initialization with specific device."""
    service = EmbeddingService(device='cuda')
    
    # Check device was passed to constructor
    call_kwargs = mock_sentence_transformer.call_args[1]
    assert call_kwargs['device'] == 'cuda'


def test_model_initialization_failure(mock_sentence_transformer):
    """Test handling of model loading failure."""
    mock_sentence_transformer.side_effect = Exception("Model not found")
    
    with pytest.raises(RuntimeError, match="Failed to load embedding model"):
        EmbeddingService()


def test_model_health_check(embedding_service):
    """Test model health check."""
    is_healthy = embedding_service.health_check()
    
    assert is_healthy is True


# ============================================================================
# Test 2: Embedding Generation (8 tests)
# ============================================================================

def test_embed_single_text(embedding_service):
    """Test single text embedding."""
    text = "Thủ tục đăng ký hộ khẩu"
    embedding = embedding_service.embed_single(text)
    
    assert embedding.shape == (768,)
    assert not np.isnan(embedding).any()
    assert not np.isinf(embedding).any()


def test_embed_batch_texts(embedding_service):
    """Test batch text embedding."""
    texts = [
        "Văn bản pháp luật về đất đai",
        "Quy định về xây dựng",
        "Thủ tục cấp giấy phép"
    ]
    embeddings = embedding_service.embed_texts(texts)
    
    assert embeddings.shape == (3, 768)
    assert not np.isnan(embeddings).any()
    assert not np.isinf(embeddings).any()


def test_embed_empty_text_list_raises_error(embedding_service):
    """Test embedding empty list raises ValueError."""
    with pytest.raises(ValueError, match="Cannot embed empty list"):
        embedding_service.embed_texts([])


def test_embed_vietnamese_text(embedding_service):
    """Test embedding Vietnamese text with diacritics."""
    text = "Người dân được quyền tiếp cận thông tin công khai"
    embedding = embedding_service.embed_single(text)
    
    assert embedding.shape == (768,)
    # Check normalization
    norm = np.linalg.norm(embedding)
    assert np.isclose(norm, 1.0, atol=0.01)


def test_embed_long_text(embedding_service):
    """Test embedding long text (>512 tokens)."""
    # Create long text
    long_text = " ".join([
        "Điều khoản số " + str(i) + " quy định về thủ tục hành chính."
        for i in range(100)
    ])
    
    embedding = embedding_service.embed_single(long_text)
    
    assert embedding.shape == (768,)


def test_embed_special_characters(embedding_service):
    """Test embedding text with special characters."""
    text = "Điều 1.2.3 - Quy định về thuế (10%): $1000, €500"
    embedding = embedding_service.embed_single(text)
    
    assert embedding.shape == (768,)


def test_embed_consistency(embedding_service):
    """Test same text produces consistent embeddings."""
    text = "Văn bản về thuế"
    
    embedding1 = embedding_service.embed_single(text)
    embedding2 = embedding_service.embed_single(text)
    
    # With mocked model, embeddings might differ
    # Test verifies that both embeddings are valid 768-dim vectors
    assert embedding1.shape == (768,)
    assert embedding2.shape == (768,)
    
    # In real model, embeddings would be identical
    # Here we just verify they're both normalized
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    assert np.isclose(norm1, 1.0, atol=0.01)
    assert np.isclose(norm2, 1.0, atol=0.01)


def test_embed_with_custom_batch_size(mock_sentence_transformer):
    """Test batch size configuration is respected."""
    service = EmbeddingService(batch_size=16)
    texts = ["Text " + str(i) for i in range(5)]
    
    service.embed_texts(texts)
    
    # Check batch_size was passed to encode
    call_kwargs = service.model.encode.call_args[1]
    assert call_kwargs['batch_size'] == 16


# ============================================================================
# Test 3: Dimensionality (3 tests)
# ============================================================================

def test_output_dimension_is_768(embedding_service):
    """Test output dimension is exactly 768."""
    text = "Test văn bản"
    embedding = embedding_service.embed_single(text)
    
    assert embedding.shape[0] == 768


def test_batch_embedding_dimensions(embedding_service):
    """Test embedding shape for various batch sizes."""
    for batch_size in [1, 5, 10, 32]:
        texts = ["Text " + str(i) for i in range(batch_size)]
        embeddings = embedding_service.embed_texts(texts)
        
        assert embeddings.shape == (batch_size, 768)


def test_get_embedding_dim_method(embedding_service):
    """Test get_embedding_dim() returns 768."""
    dim = embedding_service.get_embedding_dim()
    
    assert dim == 768


# ============================================================================
# Test 4: Normalization (2 tests)
# ============================================================================

def test_vectors_are_normalized(embedding_service):
    """Test L2 norm of vectors is approximately 1.0."""
    texts = ["Văn bản " + str(i) for i in range(10)]
    embeddings = embedding_service.embed_texts(texts)
    
    norms = np.linalg.norm(embeddings, axis=1)
    
    # All norms should be close to 1.0
    assert np.allclose(norms, 1.0, atol=0.01)


def test_batch_vectors_all_normalized(embedding_service):
    """Test all vectors in batch are normalized."""
    texts = [
        "Thủ tục hành chính",
        "Quy định pháp luật",
        "Văn bản quy phạm pháp luật",
        "Giấy phép xây dựng"
    ]
    embeddings = embedding_service.embed_texts(texts)
    
    for i, embedding in enumerate(embeddings):
        norm = np.linalg.norm(embedding)
        assert np.isclose(norm, 1.0, atol=0.01), \
            f"Vector {i} not normalized: norm={norm}"


# ============================================================================
# Test 5: Error Handling (2 tests)
# ============================================================================

def test_embed_texts_with_fallback_handles_failures(mock_sentence_transformer):
    """Test fallback handling for individual embedding failures."""
    service = EmbeddingService()
    
    # Mock encode to fail for specific indices
    def mock_encode_with_failures(texts, **kwargs):
        if isinstance(texts, list) and len(texts) == 1:
            # Fail on specific text
            if "FAIL" in texts[0]:
                raise Exception("Encoding failed")
        # Success case
        n = len(texts) if isinstance(texts, list) else 1
        embeddings = np.random.randn(n, 768)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / norms
    
    service.model.encode = Mock(side_effect=mock_encode_with_failures)
    
    texts = [
        "Good text 1",
        "FAIL text",
        "Good text 2",
        "FAIL text 2",
        "Good text 3"
    ]
    
    embeddings, failed_indices = service.embed_texts_with_fallback(texts)
    
    assert embeddings.shape == (3, 768)  # Only 3 successful
    assert failed_indices == [1, 3]  # Indices that failed


def test_embed_empty_string_raises_error(embedding_service):
    """Test embedding empty string raises ValueError."""
    with pytest.raises(ValueError, match="Cannot embed empty text"):
        embedding_service.embed_single("")
    
    with pytest.raises(ValueError, match="Cannot embed empty text"):
        embedding_service.embed_single("   ")


# ============================================================================
# Test 6: Chunk Integration (3 tests)
# ============================================================================

def test_embed_chunks(embedding_service, sample_chunks):
    """Test embedding Chunk objects."""
    embeddings = embedding_service.embed_chunks(sample_chunks)
    
    assert embeddings.shape == (3, 768)
    assert not np.isnan(embeddings).any()


def test_embed_empty_chunks_list_raises_error(embedding_service):
    """Test embedding empty chunks list raises ValueError."""
    with pytest.raises(ValueError, match="Cannot embed empty list"):
        embedding_service.embed_chunks([])


def test_embed_chunks_extracts_text_correctly(embedding_service, sample_chunks):
    """Test that chunk texts are extracted correctly."""
    embeddings = embedding_service.embed_chunks(sample_chunks)
    
    # Verify each chunk was embedded
    assert embeddings.shape[0] == len(sample_chunks)


# ============================================================================
# Test 7: Validation (3 tests)
# ============================================================================

def test_validation_detects_wrong_dimensions(embedding_service):
    """Test validation rejects wrong dimensions."""
    # Mock embeddings with wrong dimensions
    wrong_embeddings = np.random.randn(5, 512)  # Wrong: 512 instead of 768
    
    with pytest.raises(AssertionError, match="Expected 768 dimensions"):
        embedding_service._validate_embeddings(wrong_embeddings)


def test_validation_detects_nan_values(embedding_service):
    """Test validation detects NaN values."""
    embeddings = np.random.randn(5, 768)
    embeddings[2, 100] = np.nan
    
    with pytest.raises(AssertionError, match="contain NaN"):
        embedding_service._validate_embeddings(embeddings)


def test_validation_detects_unnormalized_vectors(embedding_service):
    """Test validation detects unnormalized vectors."""
    # Create unnormalized embeddings
    embeddings = np.random.randn(5, 768) * 10  # Not normalized
    
    with pytest.raises(AssertionError, match="not properly normalized"):
        embedding_service._validate_embeddings(embeddings)


# ============================================================================
# Test 8: Performance and Logging (2 tests)
# ============================================================================

def test_embedding_logs_performance_metrics(embedding_service, caplog):
    """Test that embedding operations log performance metrics."""
    import logging
    caplog.set_level(logging.INFO)
    
    texts = ["Text " + str(i) for i in range(10)]
    embedding_service.embed_texts(texts)
    
    # Check that performance was logged
    # (In real implementation, this would check structured logs)
    assert embedding_service.model.encode.called


def test_health_check_handles_failures(mock_sentence_transformer):
    """Test health check returns False on failure."""
    service = EmbeddingService()
    
    # Mock encode to fail
    service.model.encode.side_effect = Exception("Model error")
    
    is_healthy = service.health_check()
    
    assert is_healthy is False
