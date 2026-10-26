# CHANGELOG

## 2026-10-24 - P0: corpus pháp luật + API nạp tài liệu + fix RAG

- `backend/scripts/fetch_docs.py` — tải PDF Công Báo, merge phần, verify text layer | Vi sao: bản signed trên vanban.chinhphu.vn là scan, P0 không OCR.
- `backend/scripts/ingest.py` — CLI nạp `data/raw`, `--reset`, tự rebuild BM25 | Vi sao: cần nạp lại corpus lặp lại được, không thao tác tay.
- `backend/data/sources.json` — manifest 3 văn bản (150/2025/NĐ-CP, 151/2025/NĐ-CP, 65/2025/QH15) | Vi sao: nguồn tải phải tái lập được.
- `backend/app/api/documents.py` — thêm upload/status/stats | Vi sao: người dùng cần nạp tài liệu qua HTTP thay vì CLI.
- `backend/app/main.py` — mount documents router | Vi sao: endpoint mới chưa được expose.
- `backend/app/rag/ingestion/pipeline.py` — nhận `document_id`, thêm `derive_document_id` | Vi sao: ID ổn định để upsert, tránh trùng chunk khi nạp lại.
- `backend/app/database/vector_store.py` — `add` → `upsert`, thêm `count` | Vi sao: nạp lại cùng văn bản không tạo bản ghi trùng.
- `backend/app/rag/retrieval/index_manager.py` — rebuild BM25 từ toàn bộ chunk Chroma | Vi sao: BM25S không incremental, Chroma là source of truth.
- `backend/app/rag/retrieval/hybrid_retriever.py` — lọc cosine trước RRF, tắt reranker EN, persist BM25 opt-in | Vi sao: threshold 0.7 lọc sạch kết quả; test từng ghi đè index production.
- `backend/app/rag/generation/output_validator.py` — max 2500 ký tự, bỏ "có thể" khỏi từ cấm | Vi sao: câu trả lời liệt kê đúng vẫn bị chặn oan.
- `backend/app/core/dependencies.py` — truyền settings cho retriever, cache pipeline, evidence 0.25 | Vi sao: cấu hình retrieval có hiệu lực và giảm false-positive hallucination.
- `backend/app/core/config.py` — thêm `retrieval_min_similarity`, `retrieval_use_reranking`, `upload_dir` | Vi sao: tách ngưỡng retrieval khỏi code cứng.
- `backend/app/rag/ingestion/chunker.py` — fallback toàn văn khi không có section | Vi sao: TXT ngắn toàn heading bị rơi hết chunk.
- `backend/app/rag/ingestion/loader.py` — metadata `filename` → `file_name` | Vi sao: khớp schema metadata của Chroma/API.
- `backend/tests/conftest.py` — load `.env` trước khi import app | Vi sao: test API không có `GEMINI_API_KEY`.
- `backend/tests/unit/test_bm25_index.py` — chuyển sang `BM25SIndex` | Vi sao: module cũ `rank_bm25` đã bị thay.
- `backend/tests/unit/test_document_loader.py` — nhúng font Unicode khi tạo PDF test | Vi sao: pypdf/fitz đọc tiếng Việt không dấu nếu thiếu font.
- `.gitignore` — ignore `chroma_db/`, track `data/sources.json` | Vi sao: tránh commit DB runtime nhưng vẫn giữ manifest nguồn.

Kết quả: 569 chunk trong `vietnamese_documents`; 257 unit/API test pass; upload API và `/api/v1/chat/query` chạy thật với Gemini trả lời có trích dẫn.

## 2026-10-24 - P1: Auth + PostgreSQL + lịch sử hội thoại + OCR scan

- `backend/app/core/config.py` — thêm `DATABASE_URL`, JWT, OCR settings | Vi sao: P1 cần cấu hình DB/auth và OCR không hard-code.
- `backend/app/core/security.py` — bcrypt hash + JWT create/decode | Vi sao: xác thực người dùng và phân quyền admin.
- `backend/app/database/base.py`, `session.py` — async SQLAlchemy engine/session | Vi sao: lưu user, hội thoại, tin nhắn vào PostgreSQL.
- `backend/app/models/db_models.py` — User, Conversation, Message | Vi sao: schema quan hệ cho auth và lịch sử chat.
- `backend/app/schemas/auth.py`, `conversation.py` — Pydantic request/response | Vi sao: validate email/mật khẩu và serialize UUID.
- `backend/app/repositories/users.py`, `conversations.py` — truy vấn DB | Vi sao: tách SQL khỏi API, dễ test.
- `backend/app/services/auth.py`, `conversations.py` — đăng ký/đăng nhập, shape response | Vi sao: giữ API mỏng và tái sử dụng logic.
- `backend/app/api/auth.py`, `users.py`, `conversations.py`, `admin.py` — endpoint auth/user/chat history/admin | Vi sao: hoàn thiện MVP quản lý người dùng và lịch sử.
- `backend/app/api/chat.py` — lưu user/assistant message khi có token | Vi sao: chat có lịch sử, khách vẫn dùng được không cần đăng nhập.
- `backend/app/api/documents.py` — list/delete tài liệu (admin) | Vi sao: quản trị viên cần xem/xóa tài liệu đã nạp.
- `backend/app/database/vector_store.py`, `pipeline.py` — lưu `filename`, `list_documents` | Vi sao: API quản lý tài liệu cần tên file và số chunk.
- `backend/app/rag/ingestion/loader.py` — OCR fallback trang scan bằng tesseract | Vi sao: PDF scan không có text layer vẫn nạp được.
- `backend/scripts/init_db.py`, `create_admin.py` — tạo bảng và tài khoản admin | Vi sao: setup P1 không cần SQL thủ công.
- `backend/tests/api/test_p1_api.py`, `tests/unit/test_ocr_loader.py` — test auth/hội thoại/quản lý tài liệu/OCR | Vi sao: chống hồi quy khi thêm DB và OCR.
- `backend/pytest.ini` — bật `asyncio_mode=auto` | Vi sao: test async dùng fixture DB SQLite.
- `backend/requirements.txt`, `.env.example` — thêm SQLAlchemy/asyncpg/PyJWT/pytesseract | Vi sao: khai báo dependency P1.
- `docker-compose.yml` — service PostgreSQL 16 | Vi sao: chạy DB local không cần cài system package.
- `.gitignore` — track `app/models/*.py`, ignore `chroma_db/` | Vi sao: `models/` cũ che mất source model mới.

Kết quả: 270 unit/API test pass; auth + chat lịch sử + admin stats + list tài liệu chạy thật với PostgreSQL 16 (Docker); OCR code sẵn sàng, chờ cài `tesseract-ocr-vie` để verify PDF scan.

## 2026-10-24 - P2: golden set 50 câu + evaluation + fix chunker oversized

- `backend/app/rag/ingestion/chunker.py` — split section sau khi merge heading với paragraph lớn, không merge final section nếu vượt `max_size` | Vi sao: chunk 6/7/28 vượt 1000 ký tự do merge không kiểm tra giới hạn.
- `backend/tests/unit/test_semantic_chunker.py` — thêm test heading nhỏ + paragraph lớn vẫn bị chặn kích thước | Vi sao: chống hồi quy lỗi chunk oversized.
- `backend/scripts/ingest.py` — chạy `--reset` nạp lại corpus, rebuild BM25 | Vi sao: áp dụng chunker mới cho toàn bộ 3 văn bản.
- `backend/app/rag/evaluation/metrics.py` — Precision/Recall/HitRate/MRR/nDCG/MAP thuần Python | Vi sao: đo retrieval không phụ thuộc LLM, kết quả lặp lại được.
- `backend/app/rag/evaluation/evaluator.py` — load dataset, RetrievalEvaluator, AnswerEvaluator deterministic | Vi sao: đánh giá citation/term/abstention thay vì LLM judge thiếu ổn định.
- `backend/app/rag/evaluation/__init__.py` — export API evaluation | Vi sao: script và test dùng chung interface.
- `backend/scripts/evaluate.py` — CLI `--dataset/--k/--alpha/--min-similarity/--answer-eval/--output` | Vi sao: tune retrieval và lưu baseline không cần viết script tạm.
- `backend/evaluation/questions.jsonl` — 50 câu bám 3 văn bản, nhãn `document_id#chunk_index` | Vi sao: cần golden set cố định để so sánh cấu hình.
- `backend/evaluation/baselines/alpha06.json` — baseline alpha 0.6, đã lược `retrieved_details` | Vi sao: giữ report gọn, tái lập được kết quả.
- `backend/evaluation/README.md` — schema, nguồn, cách chạy, baseline và trade-off alpha | Vi sao: người sau biết cách dùng và cập nhật dataset.
- `backend/evaluation/baselines/sweep_alpha_min_sim.json` — sweep 7 alpha × 4 min_similarity | Vi sao: lưu bằng chứng chọn alpha=0.6 thay vì chỉ ghi kết luận.
- `backend/tests/unit/test_evaluation.py` — 12 test metrics/dataset/evaluator | Vi sao: chống hồi quy công thức và validate nhãn.
- `.gitignore` — exception track `backend/evaluation/baselines/*.json` | Vi sao: baseline cần lưu bền dù repo ignore `*.json`.
- `backend/scripts/setup_tesseract_local.sh` — tải `.deb`, giải nén Tesseract + vie vào `.tesseract/`, tạo wrapper | Vi sao: máy không có sudo vẫn OCR được PDF scan.
- `backend/docs/OCR_SETUP.md` — hướng dẫn cài/kiểm tra OCR, kết quả test 20 trang | Vi sao: OCR trước đây bị chặn vì thiếu binary, cần quy trình tái lập.
- `.gitignore` — ignore `backend/.tesseract/` | Vi sao: không commit binary/thư viện tải về.
- `backend/app/core/config.py` — thêm `CORS_ORIGINS`, property parse danh sách origin | Vi sao: không mở CORS `*` cho mọi website ở môi trường thật.
- `backend/app/main.py` — CORS theo allowlist, tự tắt credentials nếu cấu hình `*` | Vi sao: browser từ chối wildcard + credentials, cần cấu hình hợp lệ.
- `backend/app/api/documents.py` — upload tài liệu yêu cầu admin | Vi sao: trước đây người lạ có thể nạp/xóa dữ liệu corpus qua API.
- `backend/tests/api/test_p1_api.py` — test upload 401/403 và CORS allow/deny | Vi sao: khóa hành vi bảo mật, tránh mở lại khi refactor.
- `backend/.env.example` — thêm `CORS_ORIGINS` mặc định local frontend | Vi sao: dev chạy được mà không phải sửa code.
- `backend/app/rag/generation/llm_service.py` — prompt kèm `document_id`/chunk/heading | Vi sao: model từng trả lời “không thấy số hiệu” dù chunk đúng đã được retrieve.
- `backend/tests/unit/test_llm_service.py` — test prompt chứa `document_id` và chunk index | Vi sao: khóa metadata nguồn trong prompt, tránh hồi quy.
- `frontend/index.html` — thêm sidebar lịch sử, form đăng nhập/đăng ký, nút hội thoại mới | Vi sao: API auth/history đã có nhưng UI chỉ chat ẩn danh.
- `frontend/script.js` — token localStorage, login/register, tải lịch sử, gửi `conversation_id` | Vi sao: chat có thể lưu và xem lại hội thoại.
- `frontend/style.css` — layout sidebar + modal + responsive mobile | Vi sao: giao diện mới cần hiển thị đúng trên desktop/mobile.
- `frontend/README.md`, `QUICKSTART.md` — cập nhật tính năng, CORS, câu hỏi mẫu đúng corpus | Vi sao: tài liệu cũ hướng dẫn câu hỏi không có trong dữ liệu.

Kết quả: corpus 690 chunk (150: 59, 151: 481, 65: 150; max lần lượt 998/1000/997); 287 test pass; baseline alpha 0.6 đạt HitRate@5 0.82, Recall@5 0.81, MRR 0.604; answer eval chạy thật với Gemini.
