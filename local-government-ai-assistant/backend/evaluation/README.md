# Bộ đánh giá RAG (golden set)

Thư mục này chứa bộ câu hỏi chuẩn để đo chất lượng truy xuất và câu trả lời của trợ lý hành chính. Đây là **golden set để đánh giá**, không phải dữ liệu huấn luyện và không dùng để fine-tune.

## Nguồn dữ liệu

50 câu hỏi được xây dựng bám sát 3 văn bản pháp luật đang có trong corpus:

| Văn bản | Số câu | Nội dung chính |
|---|---:|---|
| Nghị định 150/2025/NĐ-CP | 14 | Tổ chức cơ quan chuyên môn thuộc UBND cấp tỉnh và cấp xã |
| Nghị định 151/2025/NĐ-CP | 20 | Chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức |
| Luật 65/2025/QH15 | 16 | Tổ chức chính quyền địa phương 2 cấp |

Nguồn chính thức: [vanban.chinhphu.vn](https://vanban.chinhphu.vn). Mỗi bản ghi có `source_url` để tra cứu.

Phân bố:

- `answer_type`: factual 22, list 20, definition 6, yes_no 2.
- `difficulty`: easy 21, medium 25, hard 4.

## Schema

File `questions.jsonl`, mỗi dòng là một JSON object:

```json
{
  "id": "q001",
  "question": "...",
  "expected_answer": "...",
  "relevant_documents": ["150-2025-ND-CP"],
  "relevant_chunks": ["150-2025-ND-CP#3"],
  "expected_citations": ["150/2025-NĐ-CP, Điều 1"],
  "answer_type": "factual",
  "difficulty": "easy",
  "source_url": "https://vanban.chinhphu.vn"
}
```

- `relevant_chunks` dùng khóa `"<document_id>#<chunk_index>"`, cũng chấp nhận object `{"document_id": "...", "chunk_index": 3}`.
- `id` phải duy nhất; mỗi câu phải có ít nhất một chunk liên quan.
- Chunk index được chốt theo corpus **690 chunk** sau lần ingest gần nhất. Nếu ingest lại làm thay đổi thứ tự chunk, phải export lại chunk và cập nhật nhãn.

## Chạy đánh giá

Từ `backend/`:

```bash
# Retrieval, mặc định alpha=0.6, k=1 3 5 10
.venv/bin/python scripts/evaluate.py

# Chọn cấu hình và lưu report
.venv/bin/python scripts/evaluate.py \
  --alpha 0.6 --min-similarity 0.25 --k 1 3 5 10 \
  --output evaluation/results/alpha06.json

# Đánh giá thêm câu trả lời (gọi Gemini)
.venv/bin/python scripts/evaluate.py --answer-eval --limit 10

# Chạy nhanh, không ghi file
.venv/bin/python scripts/evaluate.py --limit 5 --no-save
```

Report gồm `metrics_by_k`, `mrr`, `map`, `document_hit_rate` và `per_query_results`. Nếu dùng `--answer-eval`, report có thêm `answer_evaluation`.

## Kết quả baseline

Cấu hình: `alpha=0.6`, `min_similarity=0.25`, corpus 690 chunk. Report đầy đủ (đã lược `retrieved_details`) ở `evaluation/baselines/alpha06.json`.

| Metric | Giá trị |
|---|---:|
| HitRate@5 | 0.82 |
| Recall@5 | 0.81 |
| MRR | 0.604 |
| MAP | 0.588 |
| nDCG@5 | 0.641 |
| Document HitRate | 1.00 |

Tham khảo trade-off khi tune:

| alpha | P@1 | Recall@5 | HitRate@5 | MRR | MAP | nDCG@5 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.54 | 0.75 | 0.76 | 0.642 | 0.632 | 0.656 |
| 0.6 | 0.48 | **0.81** | **0.82** | 0.604 | 0.588 | 0.641 |

Chọn `alpha=0.6` vì pipeline dùng top-5 để sinh câu trả lời, ưu tiên Recall@5/HitRate@5 hơn P@1.

Sweep đầy đủ `alpha ∈ {0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0}` × `min_similarity ∈ {0.15, 0.20, 0.25, 0.30}` nằm ở `evaluation/baselines/sweep_alpha_min_sim.json`. Với corpus hiện tại, `min_similarity` 0.15–0.25 cho kết quả giống nhau; 0.30 làm giảm Recall@5/HitRate@5. Giữ `min_similarity=0.25` để vẫn lọc được ứng viên yếu.

## Lưu ý

- Chunk text đã được chuẩn hóa lowercase, nên `expected_answer` và `expected_citations` được so khớp không phân biệt hoa thường.
- Answer evaluation là deterministic: đo citation precision/recall, expected term recall và abstention rate; không dùng LLM judge.
- `evaluation/results/` bị `.gitignore` bỏ qua; baseline được lưu bền trong `evaluation/baselines/`.
