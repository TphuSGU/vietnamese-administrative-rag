# Báo cáo đánh giá An Phú (Phase 10)

- **Ngày chạy:** 2026-11-07 (baseline so sánh: 2026-11-03)
- **Bộ câu hỏi vàng:** `evaluation/an_phu_questions.jsonl` — 30 câu
  (10 văn bản local, 10 TTHC, 5 lịch làm việc, 5 profile/liên hệ)
- **Report JSON:** `evaluation/results/an_phu_answer_eval_2026-11-07.json`
- **Baseline:** `evaluation/baselines/an_phu_answer_eval.json`

## 1. Cấu hình chạy

| Tham số | Giá trị |
|---|---|
| `k` | 5 |
| `alpha` (vector weight) | 0.6 |
| `min_similarity` | 0.25 |
| `locality_code` | `25975` (Phường An Phú) |
| LLM | `gemini-3.1-flash-lite` |
| Embedding | `bkai-foundation-models/vietnamese-bi-encoder` (768d) |
| Corpus | 23.949 chunk — central 13.660 / local 8.103 / hcmc 2.186 |

## 2. Kết quả retrieval (30 câu)

| Chỉ số | 2026-11-07 | Baseline 11-03 | Mục tiêu |
|---|---:|---:|---:|
| HitRate@5 | **1.000** | 1.000 | ≥ 0.80 ✅ |
| Recall@5 | 1.000 | 1.000 | — |
| Precision@5 | 0.200 | 0.200 | — |
| NDCG@5 | 0.905 | 0.911 | — |
| MRR | 0.873 | 0.881 | — |
| Doc HitRate | 1.000 | 1.000 | — |

## 3. Kết quả answer-level (30 câu, có sinh câu trả lời)

| Chỉ số | 2026-11-07 | Baseline 11-03 |
|---|---:|---:|
| Citation recall | **1.000** | 1.000 |
| Citation precision | 0.470 | 0.474 |
| Expected term recall | **0.963** | 0.944 |
| Abstention rate | 0.067 | 0.033 |
| Câu rỗng `source_chunks` (refusal) | **0** | 0 |
| URL trong câu trả lời | **0** | 0 |
| Câu qua `OutputValidator` citation | **30/30 (100%)** | 30/30 |

## 4. Đối chiếu mục tiêu phase

| Mục tiêu (§9.2 / Phase 10) | Trạng thái |
|---|---|
| `retrieval@5 ≥ 80%` | ✅ 100% |
| `citation_accuracy = 100%` | ✅ 30/30 câu trả lời đều qua kiểm tra citation của `OutputValidator` (citation lấy từ metadata retrieval, không bịa số hiệu) |
| `url_in_citation = 0` | ✅ 0 URL trong answer; API test khẳng định `source_chunks[].citation` không chứa `http` |
| `hallucinated_doc_number = 0` | ✅ validator chỉ chấp nhận số hiệu/nhãn có trong context |
| Trả citation ≥ 20/30 câu | ✅ 30/30 |
| Citation recall = 100% | ✅ 1.000 |

## 5. Chẩn đoán và sửa lỗi 3 câu lịch làm việc (q023–q025)

**Triệu chứng (eval 2026-11-06):** q023/q024/q025 trả lời từ chối
("Xin lỗi, tôi chưa tìm thấy thông tin…") với `source_chunks=[]` →
citation recall 0.9, term recall 0.863.

**Đã loại trừ:**
- Metadata: 252/252 chunk lịch có `citation` đầy đủ, `doc_number=None`.
- Dữ liệu: đủ 3 tuần cần tra (12–17/01/2026, 29/6–5/7/2026, 13–4→18/4/2026).
- Retrieval: đúng doc trong top-5 (rank 1/1/3).

**Nguyên nhân:** label lịch có dạng
`"Lịch làm việc UBND phường An Phú: Lịch làm việc HĐND - UBND ngày …"`,
nhưng model trích **phần đuôi sau dấu `:`** (đúng câu chữ nguồn, thiếu tiền tố
local). `_check_citation` trước đây chỉ match **full label** → fail 2 lần
(k=5 rồi k=10) → pipeline trả refusal rỗng sources.

**Sửa (2026-11-07):**
1. `_check_citation` nhận thêm **phần đuôi sau dấu `:` của label** khi đuôi
   normalized ≥ 20 ký tự (vẫn nhận dạng đúng văn bản qua ngày/số hiệu).
2. Thêm chặn **URL** trong `OutputValidator.validate` và `validate_direct`
   (Phase 8 yêu cầu "Không có URL" nhưng chưa được cài).

**Kết quả sau sửa:** q023–q025 recall = 1.0, term = 1.0, không còn câu rỗng
nguồn trên toàn bộ 30 câu.

## 6. Ghi chú về các chỉ số

- **Citation precision** (0.470) là precision của *top-5 chunk truy xuất*
  so với tập relevant (mỗi câu thường chỉ 1 doc liên quan) — bị chặn trên
  bởi `k=5`, không phải độ chính xác trích dẫn trong câu trả lời. Đo "answer
  accuracy" bằng số câu qua `OutputValidator` = 100% (mục §9.2
  `citation_accuracy`).
- **abstention 0.067 (2 câu — ap-q021, ap-q022):** model trả lời đủ nội dung
  lịch nhưng kèm câu caveat "không tìm thấy thông tin đầy đủ" (tuần đó corpus
  chỉ có vài ngày chi tiết) — câu trả lời trung thực, recall vẫn 1.0.
  Flag `abstained` chỉ match câu chữ, không phản ánh từ chối thật.
- **ap-q029 term recall = 0.0:** lỗi tokenize khoảng thời gian
  (`07:30-11:30` vs `07:30`/`11:30`) — có từ baseline; câu trả lời thực tế
  đúng đủ giờ làm việc.

## 7. Lệnh chạy lại

```bash
cd local-government-ai-assistant/backend
source .venv/bin/activate

# Eval truy xuất + answer (30 câu, gọi Gemini)
python scripts/evaluate.py \
  --dataset evaluation/an_phu_questions.jsonl \
  --k 5 --alpha 0.6 --min-similarity 0.25 --locality-code 25975 \
  --answer-eval \
  --output evaluation/results/an_phu_answer_eval_2026-11-07.json

# Unit + API
python -m pytest -q          # 477 passed, 3 skipped, 1 deselected

# Integration thật với An Phú
python -m pytest tests/integration/test_an_phu_ingestion.py -q -m real_ingestion
```
