"""
Example usage of EmbeddingService with vietnamese-bi-encoder model.

This example demonstrates:
1. Model initialization
2. Single text embedding
3. Batch text embedding
4. Embedding Chunk objects
5. Error handling with fallback
6. Model health check
"""
import sys
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.embedding.embedding_service import EmbeddingService
from app.models.data_models import Chunk


def example_1_basic_initialization():
    """Example 1: Initialize the embedding service."""
    print("=" * 70)
    print("Example 1: Basic Initialization")
    print("=" * 70)
    
    # Initialize with defaults
    service = EmbeddingService()
    
    print(f"✅ Model loaded: {service.MODEL_NAME}")
    print(f"✅ Embedding dimensions: {service.get_embedding_dim()}")
    print(f"✅ Batch size: {service.batch_size}")
    print(f"✅ Device: {service.device}")
    
    # Health check
    if service.health_check():
        print("✅ Health check: PASSED")
    else:
        print("❌ Health check: FAILED")
    
    return service


def example_2_single_text_embedding(service):
    """Example 2: Embed a single text (query use case)."""
    print("\n" + "=" * 70)
    print("Example 2: Single Text Embedding")
    print("=" * 70)
    
    # Vietnamese query
    query = "Thủ tục đăng ký hộ khẩu tại Hà Nội như thế nào?"
    
    print(f"\n📝 Query: {query}")
    
    # Generate embedding
    embedding = service.embed_single(query)
    
    print(f"\n✅ Embedding shape: {embedding.shape}")
    print(f"✅ First 10 values: {embedding[:10]}")
    
    # Verify normalization
    norm = np.linalg.norm(embedding)
    print(f"✅ L2 norm: {norm:.6f} (should be ≈ 1.0)")
    
    return embedding


def example_3_batch_embedding(service):
    """Example 3: Embed multiple texts in batch."""
    print("\n" + "=" * 70)
    print("Example 3: Batch Text Embedding")
    print("=" * 70)
    
    # Multiple Vietnamese texts
    texts = [
        "Quy định về thuế thu nhập cá nhân năm 2024",
        "Thủ tục cấp giấy phép xây dựng nhà ở",
        "Hồ sơ đăng ký kinh doanh cần những gì?",
        "Văn bản về bảo hiểm xã hội bắt buộc",
        "Quy trình xin visa du lịch"
    ]
    
    print(f"\n📚 Embedding {len(texts)} texts:")
    for i, text in enumerate(texts, 1):
        print(f"  {i}. {text[:50]}...")
    
    # Generate embeddings
    embeddings = service.embed_texts(texts)
    
    print(f"\n✅ Embeddings shape: {embeddings.shape}")
    print(f"✅ Expected: ({len(texts)}, 768)")
    
    # Verify all are normalized
    norms = np.linalg.norm(embeddings, axis=1)
    print(f"\n✅ L2 norms:")
    for i, norm in enumerate(norms, 1):
        print(f"  Text {i}: {norm:.6f}")
    
    return embeddings


def example_4_chunk_embedding(service):
    """Example 4: Embed Chunk objects (document ingestion use case)."""
    print("\n" + "=" * 70)
    print("Example 4: Embedding Chunk Objects")
    print("=" * 70)
    
    # Create sample chunks (simulating output from SemanticChunker)
    chunks = [
        Chunk(
            text="Điều 1. Phạm vi điều chỉnh. Luật này quy định về thủ tục hành chính trong lĩnh vực xây dựng.",
            document_id="doc_001",
            chunk_index=0,
            heading_context="Chương I - Quy định chung",
            char_start=0,
            char_end=98
        ),
        Chunk(
            text="Điều 2. Đối tượng áp dụng. Luật này áp dụng đối với tổ chức, cá nhân có hoạt động xây dựng.",
            document_id="doc_001",
            chunk_index=1,
            heading_context="Chương I - Quy định chung",
            char_start=98,
            char_end=190
        ),
        Chunk(
            text="Điều 3. Giải thích từ ngữ. Trong Luật này, các từ ngữ dưới đây được hiểu như sau:",
            document_id="doc_001",
            chunk_index=2,
            heading_context="Chương I - Quy định chung",
            char_start=190,
            char_end=270
        )
    ]
    
    print(f"\n📦 Embedding {len(chunks)} chunks:")
    for chunk in chunks:
        print(f"  • [{chunk.heading_context}] {chunk.text[:60]}...")
    
    # Generate embeddings
    embeddings = service.embed_chunks(chunks)
    
    print(f"\n✅ Embeddings shape: {embeddings.shape}")
    print(f"✅ Ready for ChromaDB storage")
    
    # Show how to pair embeddings with chunks
    print(f"\n📊 Chunk → Embedding mapping:")
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        print(f"  Chunk {i}: doc_id={chunk.document_id}, "
              f"index={chunk.chunk_index}, "
              f"embedding_norm={np.linalg.norm(embedding):.6f}")
    
    return embeddings, chunks


def example_5_error_handling(service):
    """Example 5: Error handling with fallback."""
    print("\n" + "=" * 70)
    print("Example 5: Error Handling with Fallback")
    print("=" * 70)
    
    # Mix of valid and potentially problematic texts
    texts = [
        "Văn bản hợp lệ số 1",
        "",  # Empty string - will fail
        "Văn bản hợp lệ số 2",
        "   ",  # Only whitespace - will fail
        "Văn bản hợp lệ số 3"
    ]
    
    print(f"\n📝 Processing {len(texts)} texts (some may fail):")
    for i, text in enumerate(texts):
        display = text if text.strip() else "[EMPTY/WHITESPACE]"
        print(f"  {i}. {display}")
    
    # Use fallback mode to handle failures gracefully
    print("\n⚠️ Using fallback mode (tolerates individual failures)...")
    
    # Manually handle empty strings to demonstrate
    valid_texts = []
    valid_indices = []
    failed_indices = []
    
    for i, text in enumerate(texts):
        if text.strip():
            valid_texts.append(text)
            valid_indices.append(i)
        else:
            failed_indices.append(i)
    
    if valid_texts:
        embeddings = service.embed_texts(valid_texts)
        
        print(f"\n✅ Successfully embedded: {len(embeddings)} texts")
        print(f"❌ Failed to embed: {len(failed_indices)} texts")
        print(f"   Failed indices: {failed_indices}")
        
        return embeddings
    else:
        print("❌ No valid texts to embed")
        return None


def example_6_semantic_similarity(service):
    """Example 6: Compute semantic similarity between texts."""
    print("\n" + "=" * 70)
    print("Example 6: Semantic Similarity Computation")
    print("=" * 70)
    
    # Query and candidate texts
    query = "Thủ tục đăng ký kinh doanh"
    
    candidates = [
        "Hồ sơ đăng ký kinh doanh gồm có những gì?",  # High similarity (same topic)
        "Cách tính thuế thu nhập doanh nghiệp",        # Medium similarity (business)
        "Quy định về xây dựng nhà ở"                   # Low similarity (different topic)
    ]
    
    print(f"\n🔍 Query: {query}")
    print(f"\n📚 Candidates:")
    for i, cand in enumerate(candidates, 1):
        print(f"  {i}. {cand}")
    
    # Embed query and candidates
    query_emb = service.embed_single(query)
    candidate_embs = service.embed_texts(candidates)
    
    # Compute cosine similarity (dot product of normalized vectors)
    similarities = np.dot(candidate_embs, query_emb)
    
    print(f"\n📊 Similarity scores (higher = more similar):")
    for i, (cand, score) in enumerate(zip(candidates, similarities), 1):
        print(f"  {i}. {score:.4f} - {cand}")
    
    # Rank by similarity
    ranked_indices = np.argsort(similarities)[::-1]
    print(f"\n🏆 Ranked results:")
    for rank, idx in enumerate(ranked_indices, 1):
        print(f"  #{rank}: {candidates[idx]} (score: {similarities[idx]:.4f})")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("EmbeddingService Examples")
    print("Using: bkai-foundation-models/vietnamese-bi-encoder")
    print("=" * 70)
    
    try:
        # Example 1: Initialize
        service = example_1_basic_initialization()
        
        # Example 2: Single text
        example_2_single_text_embedding(service)
        
        # Example 3: Batch embedding
        example_3_batch_embedding(service)
        
        # Example 4: Chunk embedding
        example_4_chunk_embedding(service)
        
        # Example 5: Error handling
        example_5_error_handling(service)
        
        # Example 6: Semantic similarity
        example_6_semantic_similarity(service)
        
        print("\n" + "=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
