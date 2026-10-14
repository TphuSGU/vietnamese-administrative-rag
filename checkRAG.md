# 🎯 **ĐẢM BẢO RAG CHÍNH XÁC - GUIDE TOÀN DIỆN**

Tuyệt vời! Đây là câu hỏi quan trọng nhất. Tôi sẽ hướng dẫn chi tiết:

---

## 📋 **MỤC LỤC**

1. [Đảm bảo Retrieval đúng](#1-đảm-bảo-retrieval-đúng)
2. [Đảm bảo LLM trả lời đúng format](#2-đảm-bảo-llm-trả-lời-đúng-format)
3. [Kiểm tra & Validation](#3-kiểm-tra--validation)
4. [Evaluation & Monitoring](#4-evaluation--monitoring)

---

## 1️⃣ **ĐẢM BẢO RETRIEVAL ĐÚNG**

### **A. Cơ chế đã implement:**Perfect! Giờ tôi tạo **COMPREHENSIVE VALIDATION GUIDE**:Tuyệt! Giờ tôi tạo guide toàn diện:

---

# 🎯 **ĐẢMNHỮNG đảm bảo CHÍNH XÁC - COMPLETE GUIDE**

## **CÁC CƠ CHẾ ĐÃ IMPLEMENT**

### ✅ **1. RETRIEVAL ACCURACY (Đã có sẵn)**

#### **A. Hybrid Search (3 layers)**
```python
┌─────────────────────────────────────┐
│  Query: "Điều 10 quy định gì?"     │
└───────────────┬─────────────────────┘
                │
        ┌───────┴───────┐
        │               │
   ┌────▼────┐     ┌───▼────┐
   │ Vector  │     │  BM25S │
   │Semantic │     │Keyword │
   │ Search  │     │ Search │
   └────┬────┘     └───┬────┘
        │              │
        └──────┬───────┘
               │
        ┌──────▼──────┐
        │ RRF Fusion  │  ← Kết hợp rankings
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │  Reranking  │  ← Cross-encoder
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │ Threshold   │  ← Filter score < 0.7
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │  Top K      │
        └─────────────┘
```

**File:** `app/rag/retrieval/hybrid_retriever.py`

**Validation points:**
- ✅ Minimum similarity threshold (0.7)
- ✅ RRF fusion (combines rankings)
- ✅ Reranking (improves order)
- ✅ K bounds validation (1-20)

---

#### **B. Output Validation (4 checks)**

**File:** `app/rag/generation/output_validator.py`

```python
def validate(answer, query, context):
    # Check 1: Structure
    ✅ Length: 20-1000 chars
    ✅ Not empty
    
    # Check 2: Vietnamese language
    ✅ Diacritics present (à, á, ...)
    ✅ Min 1% Vietnamese chars
    
    # Check 3: Evidence (MOST IMPORTANT!)
    ✅ Overlap ratio ≥ 0.4 (40% terms match context)
    ✅ No hallucination
    
    # Check 4: Confidence
    ✅ No uncertain phrases ("có thể", "có lẽ", ...)
    ✅ No hedging language
```

**Evidence Check Algorithm:**
```python
# Extract terms from answer
answer_terms = ["điều", "10", "quy", "định", "hộ", "khẩu"]

# Check against context
verified = count_terms_in_context(answer_terms, context)

# Calculate ratio
overlap = verified / len(answer_terms)  # Must be ≥ 0.4

if overlap < 0.4:
    return False, "Hallucination detected!"
```

---

### ✅ **2. LLM FORMAT CONTROL (Đã có sẵn)**

#### **A. Prompt Engineering**

**File:** `app/rag/generation/llm_service.py`

```python
PROMPT_TEMPLATE = """
BẠN LÀ trợ lý ảo hỗ trợ tra cứu thông tin hành chính.

QUY TẮC QUAN TRỌNG:
1. CHỈ trả lời dựa trên TÀI LIỆU được cung cấp
2. KHÔNG tự bịa thêm thông tin
3. Nếu không có thông tin → "Không tìm thấy..."
4. Trả lời ngắn gọn, rõ ràng bằng tiếng Việt
5. Trích dẫn nguồn nếu có (Điều X, Khoản Y)

TÀI LIỆU THAM KHẢO:
{context}

CÂU HỎI: {query}

TRẢ LỜI:
"""
```

**Format enforced by:**
- ✅ System instructions
- ✅ Context formatting
- ✅ Temperature = 0.3 (factual)
- ✅ Max tokens = 500

---

#### **B. Response Parsing**

**File:** `app/rag/generation/llm_service.py`

```python
def generate_answer(query, chunks):
    # 1. Build prompt
    prompt = build_prompt(query, chunks)
    
    # 2. Call LLM
    response = gemini_api.generate(
        prompt=prompt,
        temperature=0.3,      # Low = factual
        max_tokens=500        # Limit length
    )
    
    # 3. Extract answer
    answer = response.text.strip()
    
    # 4. Build references
    source_chunks = create_chunk_references(chunks)
    
    return GeneratedAnswer(
        answer=answer,
        source_chunks=source_chunks,
        model="gemini-2.0-flash-exp"
    )
```

---

## 📊 **3. KIỂM TRA & VALIDATION**

### **A. Automated Tests (111 tests đã có)**

```bash
cd backend

# 1. Test retrieval accuracy
pytest tests/unit/test_hybrid_retriever.py -v

# 2. Test output validation
pytest tests/integration/test_hybrid_rag_pipeline.py::test_output_validation_catches_hallucination -v

# 3. Test LLM format
pytest tests/unit/test_llm_service.py -v

# 4. Test end-to-end
pytest tests/integration/test_rag_pipeline_real.py -v
```

---

### **B. Manual Testing Script**

Tạo file `test_rag_quality.py`:

```python
"""
Manual RAG Quality Testing Script
Usage: python test_rag_quality.py
"""

import sys
sys.path.append('.')

from app.rag.pipeline.hybrid_rag_pipeline import HybridRAGPipeline
from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.embedding.embedding_service import EmbeddingService
from app.rag.generation.llm_service import LLMService
from app.rag.generation.output_validator import OutputValidator
from app.database.vector_store import VectorStore

# Test queries với expected behavior
TEST_CASES = [
    {
        "query": "Điều 10 quy định gì về hộ khẩu?",
        "expected_keywords": ["điều 10", "hộ khẩu", "đăng ký"],
        "should_contain_article": True
    },
    {
        "query": "Thủ tục làm CMND cần giấy tờ gì?",
        "expected_keywords": ["cmnd", "giấy tờ", "thủ tục"],
        "should_contain_article": True
    },
    {
        "query": "Quy định về người ngoài hành tinh?",
        "expected_keywords": [],
        "should_fail": True,  # Không có trong corpus
        "expected_response": "Không tìm thấy"
    }
]

def test_retrieval_accuracy(retriever, query, expected_keywords):
    """Test if retrieval finds relevant docs."""
    results = retriever.retrieve(query, k=5)
    
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    
    if not results:
        print("❌ No results retrieved!")
        return False
    
    # Check top result
    top_chunk = results[0]
    print(f"\n📄 Top result (score: {top_chunk.similarity_score:.3f}):")
    print(f"   {top_chunk.text[:200]}...")
    
    # Verify keywords
    text_lower = top_chunk.text.lower()
    found_keywords = [kw for kw in expected_keywords if kw in text_lower]
    
    print(f"\n🔍 Keywords found: {found_keywords}")
    
    if len(found_keywords) >= len(expected_keywords) * 0.5:  # 50% match
        print("✅ Retrieval PASSED")
        return True
    else:
        print("❌ Retrieval FAILED - keywords not found")
        return False


def test_answer_quality(pipeline, query, expected_behavior):
    """Test LLM answer quality."""
    print(f"\n{'='*60}")
    print(f"Testing Answer Quality: {query}")
    print(f"{'='*60}")
    
    # Generate answer
    response = pipeline.query(query, k=5)
    
    print(f"\n💬 Answer:")
    print(f"   {response.answer}")
    
    print(f"\n📊 Metadata:")
    print(f"   - Sources: {len(response.source_chunks)}")
    print(f"   - Processing time: {response.processing_time:.2f}s")
    print(f"   - Model: {response.model}")
    
    # Checks
    checks_passed = []
    
    # 1. Length check
    if 20 <= len(response.answer) <= 1000:
        checks_passed.append("✅ Length OK")
    else:
        checks_passed.append(f"❌ Length: {len(response.answer)}")
    
    # 2. Vietnamese check
    vietnamese_chars = sum(1 for c in response.answer if c in 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')
    if vietnamese_chars >= 5:
        checks_passed.append("✅ Vietnamese OK")
    else:
        checks_passed.append("❌ Not Vietnamese")
    
    # 3. Expected behavior
    if expected_behavior.get("should_fail"):
        if "không tìm thấy" in response.answer.lower():
            checks_passed.append("✅ Correctly says 'not found'")
        else:
            checks_passed.append("❌ Should have said 'not found'")
    
    if expected_behavior.get("should_contain_article"):
        if any(kw in response.answer.lower() for kw in expected_behavior["expected_keywords"]):
            checks_passed.append("✅ Contains expected keywords")
        else:
            checks_passed.append("❌ Missing expected keywords")
    
    # 4. Sources check
    if response.source_chunks:
        checks_passed.append(f"✅ Sources: {len(response.source_chunks)}")
    else:
        checks_passed.append("❌ No sources")
    
    print(f"\n📋 Validation:")
    for check in checks_passed:
        print(f"   {check}")
    
    return all("✅" in check for check in checks_passed)


def main():
    """Run quality tests."""
    print("🚀 Starting RAG Quality Tests...")
    
    # Initialize components
    print("\n⏳ Initializing components...")
    embedding_service = EmbeddingService()
    vector_store = VectorStore()
    llm_service = LLMService()
    validator = OutputValidator(min_evidence_ratio=0.4)
    
    retriever = HybridRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
        alpha=0.6,
        use_reranking=True
    )
    
    pipeline = HybridRAGPipeline(
        hybrid_retriever=retriever,
        llm_service=llm_service,
        output_validator=validator
    )
    
    print("✅ Components initialized")
    
    # Run tests
    results = []
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{'#'*60}")
        print(f"# TEST CASE {i}/{len(TEST_CASES)}")
        print(f"{'#'*60}")
        
        # Test retrieval
        retrieval_ok = test_retrieval_accuracy(
            retriever,
            test_case["query"],
            test_case.get("expected_keywords", [])
        )
        
        # Test answer
        answer_ok = test_answer_quality(
            pipeline,
            test_case["query"],
            test_case
        )
        
        results.append({
            "query": test_case["query"],
            "retrieval": retrieval_ok,
            "answer": answer_ok,
            "overall": retrieval_ok and answer_ok
        })
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result["overall"] else "❌ FAIL"
        print(f"\n{i}. {status}")
        print(f"   Query: {result['query'][:50]}...")
        print(f"   Retrieval: {'✅' if result['retrieval'] else '❌'}")
        print(f"   Answer: {'✅' if result['answer'] else '❌'}")
    
    # Overall
    pass_count = sum(1 for r in results if r["overall"])
    print(f"\n{'='*60}")
    print(f"Overall: {pass_count}/{len(results)} passed ({pass_count/len(results)*100:.0f}%)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
```

**Run:**
```bash
python test_rag_quality.py
```

---

### **C. Evaluation Dashboard**

Tạo file `evaluate_rag.py`:

```python
"""
RAG Evaluation with Metrics
"""

from typing import List, Dict
import json
from datetime import datetime

# Evaluation metrics
def calculate_precision_at_k(retrieved, relevant, k=5):
    """Precision@K"""
    retrieved_k = retrieved[:k]
    hits = sum(1 for doc in retrieved_k if doc in relevant)
    return hits / k if k > 0 else 0


def calculate_recall_at_k(retrieved, relevant, k=10):
    """Recall@K"""
    retrieved_k = retrieved[:k]
    hits = sum(1 for doc in retrieved_k if doc in relevant)
    return hits / len(relevant) if relevant else 0


def calculate_mrr(retrieved, relevant):
    """Mean Reciprocal Rank"""
    for i, doc in enumerate(retrieved, 1):
        if doc in relevant:
            return 1 / i
    return 0


def evaluate_rag_system(test_dataset: List[Dict]):
    """
    Evaluate RAG system on test dataset.
    
    test_dataset format:
    [
        {
            "query": "Điều 10 quy định gì?",
            "relevant_docs": ["doc_1", "doc_3"],
            "expected_answer_keywords": ["hộ khẩu", "đăng ký"]
        },
        ...
    ]
    """
    metrics = {
        "precision_at_5": [],
        "recall_at_10": [],
        "mrr": [],
        "answer_quality": []
    }
    
    # TODO: Implement với real components
    
    return {
        "timestamp": datetime.now().isoformat(),
        "test_count": len(test_dataset),
        "avg_precision_at_5": sum(metrics["precision_at_5"]) / len(metrics["precision_at_5"]),
        "avg_recall_at_10": sum(metrics["recall_at_10"]) / len(metrics["recall_at_10"]),
        "avg_mrr": sum(metrics["mrr"]) / len(metrics["mrr"])
    }
```

---

## 🎯 **4. MONITORING & LOGGING**

### **A. Query Logs**

**File:** `logs/hybrid_query_logs.jsonl`

Mỗi query được log:
```json
{
  "query_id": "uuid",
  "timestamp": 1234567890,
  "query": "Điều 10...",
  "num_chunks_retrieved": 5,
  "answer": "...",
  "validation_passed": true,
  "processing_time_ms": 1234,
  "retry_count": 0
}
```

**Xem logs:**
```bash
# Latest queries
tail -f logs/hybrid_query_logs.jsonl

# Parse JSON
cat logs/hybrid_query_logs.jsonl | jq '.'

# Failed validations
cat logs/hybrid_query_logs.jsonl | jq 'select(.validation_passed == false)'
```

---

### **B. Health Monitoring**

**API Endpoint:** `GET /api/v1/chat/health`

```bash
curl http://localhost:8000/api/v1/chat/health | jq '.'
```

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "vector_store": {
      "status": "healthy",
      "count": 1500
    },
    "embedding_service": {
      "status": "healthy"
    },
    "llm_service": {
      "status": "healthy"
    },
    "validator": {
      "status": "healthy"
    }
  }
}
```

---

## ✅ **CHECKLIST: ĐẢM BẢO CHÍNH XÁC**

### **Before Production:**
- [ ] Run all 111 tests: `pytest tests/ -v`
- [ ] Manual quality testing với `test_rag_quality.py`
- [ ] Check logs: `tail -f logs/hybrid_query_logs.jsonl`
- [ ] Test edge cases (empty results, hallucination)
- [ ] Verify Vietnamese text handling
- [ ] Test với real documents

### **Configuration Tuning:**
```bash
# .env settings to adjust
MIN_EVIDENCE_RATIO=0.4     # ↑ = Stricter validation
HYBRID_ALPHA=0.6           # Adjust vector/BM25 balance
MIN_SIMILARITY=0.7         # ↑ = Higher quality threshold
USE_RERANKING=true         # Enable for better accuracy
TEMPERATURE=0.3            # ↓ = More factual
```

---

## 🎯 **TÓM TẮT**

| Câu hỏi | Đã implement? | File | Cách kiểm tra |
|---------|---------------|------|---------------|
| Retrieval đúng? | ✅ | `hybrid_retriever.py` | `pytest tests/unit/test_hybrid_retriever.py -v` |
| LLM format đúng? | ✅ | `llm_service.py` | `pytest tests/unit/test_llm_service.py -v` |
| Validation? | ✅ | `output_validator.py` | `pytest tests/integration/test_hybrid_rag_pipeline.py -v` |
| Monitoring? | ✅ | `logs/hybrid_query_logs.jsonl` | `tail -f logs/*.jsonl` |
| Evaluation? | 🔄 | `evaluation/metrics.py` | To be expanded |

---

**🎯 BẠN ĐÃ CÓ SẴN 4 LAYERS PROTECTION:**

1. ✅ **Hybrid Retrieval** - 3 methods combined
2. ✅ **Output Validation** - 4 checks
3. ✅ **111 Automated Tests** - Comprehensive coverage
4. ✅ **Logging & Monitoring** - Track all queries

**Chạy tests ngay để verify:**
```bash
pytest tests/ -v
python test_rag_quality.py  # (tạo file này)
```