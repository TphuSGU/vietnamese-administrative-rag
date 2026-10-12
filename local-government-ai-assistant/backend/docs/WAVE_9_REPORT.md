# Wave 9: LLM Service (Google Gemini API)

## Overview

Wave 9 implements the LLM Service using Google's Gemini API for generating accurate, context-grounded answers in Vietnamese. The service constructs prompts with retrieved document chunks and system instructions to ensure responses are factual and cite sources appropriately.

## Architecture

```
Query + Retrieved Chunks
    ↓
Prompt Construction
    ↓
Google Gemini API
  (gemini-2.0-flash-exp)
    ↓
Generated Answer
    ↓
GeneratedAnswer with Sources
```

## Component Implemented

### LLMService Class

**Purpose**: Generate Vietnamese answers using Gemini with retrieved context.

**Key Features**:
- Gemini API integration with retry logic
- Vietnamese-specific system instructions
- Context-aware prompt construction
- Source chunk references
- Token estimation

**Configuration**:
```python
MODEL_NAME = "gemini-2.0-flash-exp"
MAX_TOKENS = 500
TEMPERATURE = 0.3  # Low temperature for factual responses
```

## API Reference

### LLMService

```python
class LLMService:
    def __init__(self, api_key: Optional[str] = None)
```

**Initialization**:
- `api_key`: Gemini API key (defaults to `GEMINI_API_KEY` environment variable)

**Raises**:
- `ValueError`: If API key not provided

#### Methods

**`def generate_answer(query: str, retrieved_chunks: List[RetrievedChunk]) -> GeneratedAnswer`**

Generate answer using Gemini LLM.

**Parameters**:
- `query`: User query in Vietnamese
- `retrieved_chunks`: Retrieved document chunks for context

**Returns**:
- `GeneratedAnswer` containing:
  - `answer`: Generated answer text in Vietnamese
  - `source_chunks`: List of ChunkReference objects
  - `model`: Model name used
  - `tokens_used`: Estimated token count

**Raises**:
- `LLMGenerationError`: If generation fails after retries

**Example**:
```python
llm = LLMService(api_key="your-gemini-api-key")

# Generate answer with context
answer = llm.generate_answer(
    query="Thủ tục đăng ký hộ khẩu cần những giấy tờ gì?",
    retrieved_chunks=retrieved_chunks
)

print(f"Answer: {answer.answer}")
print(f"Model: {answer.model}")
print(f"Tokens: {answer.tokens_used}")
print(f"Sources: {len(answer.source_chunks)} chunks")
```

## System Instructions

The service uses comprehensive Vietnamese system instructions:

```
Bạn là trợ lý AI hỗ trợ công dân tra cứu thông tin về văn bản chính quyền địa phương.

Nhiệm vụ của bạn:
1. Trả lời câu hỏi dựa CHÍNH XÁC trên các tài liệu được cung cấp
2. Trả lời HOÀN TOÀN bằng tiếng Việt
3. Trích dẫn nguồn tài liệu khi trả lời (ví dụ: "Theo Tài liệu 1...")
4. Nếu thông tin không đủ, hãy nói rõ "Tôi không tìm thấy thông tin..."

LƯU Ý QUAN TRỌNG:
- KHÔNG tự suy đoán hoặc tạo thông tin không có trong tài liệu
- KHÔNG trả lời về chủ đề không liên quan đến hành chính công
- CHỈ sử dụng thông tin từ các tài liệu được cung cấp
```

## Prompt Structure

### Complete Prompt Format

```
[SYSTEM_INSTRUCTION]

---

CÁC TÀI LIỆU THAM KHẢO:

[Tài liệu 1] (Điều 5 - Thủ tục đăng ký):
Để đăng ký hộ khẩu, cần có...

[Tài liệu 2] (Điều 6 - Thời gian giải quyết):
Thời gian giải quyết là 3 ngày làm việc...

---

CÂU HỎI CỦA NGƯỜI DÙNG:
Thủ tục đăng ký hộ khẩu cần những giấy tờ gì?

TRẢ LỜI (bằng tiếng Việt, dựa trên tài liệu trên):
```

### Context Formatting

Each retrieved chunk is formatted as:
```
[Tài liệu {i}] ({heading_context}):
{chunk.text}
```

## Requirements Validated

✅ **Requirement 9.1**: Use Gemini API for answer generation  
✅ **Requirement 9.2**: Construct prompt with query and context  
✅ **Requirement 9.3**: Format chunks with separators  
✅ **Requirement 9.4**: Include Vietnamese response instruction  
✅ **Requirement 9.5**: Reserved for OpenAI (not applicable)  
✅ **Requirement 9.6**: Handle insufficient information gracefully  
✅ **Requirement 9.7**: Return answer with source chunk references  
✅ **Requirement 15.3**: Retry logic (3 attempts with exponential backoff)  

## Usage Examples

### Basic Answer Generation

```python
from app.rag.generation.llm_service import LLMService
from app.models.data_models import RetrievedChunk

# Initialize service
llm = LLMService()  # Uses GEMINI_API_KEY from environment

# Prepare context
chunks = [
    RetrievedChunk(
        text="Giấy tờ cần có: CMND, sổ hộ khẩu cũ, đơn đăng ký",
        similarity_score=0.95,
        metadata={"document_id": "doc_1", "heading_context": "Điều 5"}
    ),
    RetrievedChunk(
        text="Thời gian giải quyết: 3 ngày làm việc",
        similarity_score=0.85,
        metadata={"document_id": "doc_1", "heading_context": "Điều 6"}
    )
]

# Generate answer
answer = llm.generate_answer(
    query="Thủ tục đăng ký hộ khẩu cần những giấy tờ gì?",
    retrieved_chunks=chunks
)

print(answer.answer)
# Output: "Để đăng ký hộ khẩu, bạn cần các giấy tờ sau: CMND, sổ hộ khẩu cũ, 
#          và đơn đăng ký. Thời gian giải quyết là 3 ngày làm việc."
```

### Handling Insufficient Information

```python
# Generate answer with empty context
answer = llm.generate_answer(
    query="Không có tài liệu liên quan",
    retrieved_chunks=[]
)

print(answer.answer)
# Output: "Tôi không tìm thấy tài liệu liên quan đến câu hỏi của bạn 
#          trong cơ sở dữ liệu."
```

### Accessing Source References

```python
answer = llm.generate_answer(query, chunks)

print(f"\nAnswer: {answer.answer}")
print(f"\nSources ({len(answer.source_chunks)} chunks):")
for i, source in enumerate(answer.source_chunks, 1):
    print(f"  {i}. Document: {source.document_id}")
    print(f"     Score: {source.similarity_score:.3f}")
    print(f"     Preview: {source.text[:100]}...")
```

## Error Handling & Retry Logic

### Automatic Retries

The service uses `tenacity` for automatic retries:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _call_gemini_api(self, prompt: str) -> str:
    # Gemini API call
```

**Retry Strategy**:
- Maximum 3 attempts
- Exponential backoff: 2s, 4s, 8s
- Reraise exception after exhausting retries

### Error Cases

```python
from app.models.exceptions import LLMGenerationError

try:
    answer = llm.generate_answer(query, chunks)
except LLMGenerationError as e:
    print(f"Generation failed: {e}")
    # Handle error: retry later, use fallback response, etc.
```

## Configuration

### Environment Variables

```bash
# .env file
GEMINI_API_KEY=your-gemini-api-key-here
```

Get your API key from: https://makersuite.google.com/app/apikey

### Model Parameters

```python
# Adjust generation parameters
class LLMService:
    MAX_TOKENS = 500       # Maximum response length
    TEMPERATURE = 0.3      # Creativity (0.0-1.0, lower = more factual)
    MODEL_NAME = "gemini-2.0-flash-exp"  # Gemini model
```

## Data Model

### GeneratedAnswer

```python
@dataclass
class GeneratedAnswer:
    answer: str                      # Generated answer text
    source_chunks: List[ChunkReference]  # Source references
    model: str                       # Model name used
    tokens_used: int                 # Estimated token count
```

### ChunkReference

```python
@dataclass
class ChunkReference:
    document_id: str                 # Source document ID
    text: str                        # Preview text (first 200 chars)
    similarity_score: float          # Retrieval similarity
    chunk_index: Optional[int]       # Chunk position in document
```

## Performance Characteristics

- **Latency**: ~1-3 seconds per request
- **Token Limit**: 500 tokens maximum per response
- **Retry Overhead**: Up to 14 seconds if all retries needed
- **Cost**: Gemini 2.0 Flash is free tier eligible (check Google AI limits)

## Best Practices

### 1. Provide Quality Context

```python
# Good: Relevant, focused chunks
chunks = retriever.retrieve(query, k=5)
answer = llm.generate_answer(query, chunks)

# Avoid: Too many irrelevant chunks
chunks = retriever.retrieve(query, k=20)  # May dilute context
```

### 2. Handle API Limits

```python
import time

try:
    answer = llm.generate_answer(query, chunks)
except LLMGenerationError as e:
    if "quota" in str(e).lower():
        print("API quota exceeded, waiting...")
        time.sleep(60)  # Wait 1 minute
        answer = llm.generate_answer(query, chunks)
```

### 3. Validate API Key

```python
from app.rag.generation.llm_service import LLMService

try:
    llm = LLMService()
    print("✓ LLM Service initialized successfully")
except ValueError as e:
    print(f"✗ Configuration error: {e}")
    print("  Set GEMINI_API_KEY in .env file")
```

## Testing

The LLM Service integrates seamlessly with the RAG pipeline test suite. Tests use mocking to avoid actual API calls:

```python
from unittest.mock import Mock

# Mock LLM service for testing
mock_llm = Mock()
mock_llm.generate_answer.return_value = GeneratedAnswer(
    answer="Test answer",
    source_chunks=[],
    model="gemini-2.0-flash-exp",
    tokens_used=10
)
```

Run tests:
```bash
pytest tests/integration/test_rag_pipeline_integration.py -v
```

## Troubleshooting

### API Key Issues

```
Error: Gemini API key not provided
```
**Solution**: Set `GEMINI_API_KEY` in `.env` file

### Rate Limiting

```
Error: 429 Too Many Requests
```
**Solution**: Wait 60 seconds or upgrade to paid tier

### Empty Responses

```
Answer: ""
```
**Solution**: Check that retrieved chunks contain relevant information

## Integration with RAG Pipeline

The LLM Service is integrated in Wave 10 RAG Pipeline:

```python
from app.rag.pipeline.rag_pipeline import RAGPipeline

rag = RAGPipeline(
    retriever=retriever,
    llm_service=LLMService()
)

response = rag.query("Thủ tục đăng ký hộ khẩu")
print(response.answer)
```

## Next Steps

Wave 9 LLM Service is the generation component of:
- **Wave 10**: Complete RAG Pipeline orchestration

See `WAVE_10_REPORT.md` for end-to-end RAG system documentation.
