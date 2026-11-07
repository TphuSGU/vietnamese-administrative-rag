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

## 2026-10-29 - P3.4a: Admin UI + cấu hình API + quản lý hội thoại

- `frontend/admin.html` — trang quản trị mới với tổng quan, tài liệu, người dùng | Vi sao: admin chưa có giao diện để vận hành hệ thống.
- `frontend/admin.css` — layout responsive, bảng, badge trạng thái, drop zone | Vi sao: tách style admin khỏi giao diện chat để dễ bảo trì.
- `frontend/admin.js` — gọi stats/jobs/documents/users, upload + poll job, xóa tài liệu, đổi role | Vi sao: nối UI với API sẵn có và chặn thao tác khi thiếu quyền.
- `frontend/config.js` — API base URL lấy từ runtime/query param, không hard-code trong logic | Vi sao: đổi môi trường dev/prod không phải sửa JS.
- `frontend/index.html` — thêm link Quản trị và nạp `config.js` | Vi sao: admin cần lối vào trang quản trị, frontend cần cấu hình API.
- `frontend/script.js` — lưu role, hiện link admin, đổi tên/xóa hội thoại trên sidebar | Vi sao: hoàn thiện thao tác hội thoại và phân quyền UI.
- `frontend/style.css` — style hàng hội thoại có nút Sửa/Xóa, responsive mobile | Vi sao: nút thao tác không được vỡ layout sidebar.
- `backend/app/api/conversations.py` — thêm `PATCH /conversations/{id}` đổi tên | Vi sao: UI đổi tên cần endpoint, không dùng prompt giả.
- `backend/app/schemas/conversation.py`, `repositories/conversations.py` — schema + cập nhật title | Vi sao: validate độ dài và tách truy vấn DB khỏi API.
- `backend/app/api/documents.py` — thêm `GET /documents/jobs` cho admin | Vi sao: trang quản trị cần xem lại job sau khi tải trang.
- `backend/tests/api/test_p1_api.py` — test đổi tên hội thoại và quyền xem jobs | Vi sao: khóa hành vi API mới, tránh hồi quy.
- `frontend/README.md`, `QUICKSTART.md`, `IMPLEMENTATION_SUMMARY.md` — cập nhật admin UI và cách cấu hình API URL | Vi sao: tài liệu cũ vẫn hướng dẫn hard-code `API_BASE_URL`.

Kết quả: 287 unit/API test pass; admin UI có upload + poll job + stats + danh sách/xóa tài liệu + đổi role; chat có đổi tên/xóa hội thoại; API URL cấu hình qua `config.js` hoặc `?api=`.

## 2026-10-29 - P3.4b: lọc/tìm kiếm/phân trang người dùng

- `backend/app/schemas/auth.py` — thêm `UserListResponse`, `UserRoleCounts` | Vi sao: API cần trả items + tổng + số trang + số lượng theo role thay vì list thô.
- `backend/app/repositories/users.py` — `list_users` nhận role/search/offset/limit, thêm đếm tổng và đếm theo role | Vi sao: lọc/tìm kiếm phải chạy ở DB, không tải toàn bộ user lên RAM.
- `backend/app/api/users.py` — thêm query `role/page/page_size/search`, trả response phân trang | Vi sao: admin cần lọc theo role và chuyển trang mà không phá quyền admin.
- `backend/tests/api/test_p1_api.py` — test phân trang, lọc role, tìm kiếm, role counts, đổi role | Vi sao: khóa contract mới và tránh hồi quy quyền truy cập.
- `frontend/admin.html` — thêm tab role, ô tìm kiếm, chọn page size, nút Trước/Sau, thông tin trang | Vi sao: UI cần điều khiển query API mới.
- `frontend/admin.css` — style role tabs, toolbar và pagination, responsive mobile | Vi sao: bảng người dùng nhiều điều khiển dễ vỡ layout.
- `frontend/admin.js` — state lọc/phân trang, debounce tìm kiếm, render `items/total_pages/role_counts`, reload sau đổi role | Vi sao: trước đây code giả định `/users` trả array nên lệch contract.
- `frontend/README.md` — cập nhật query users và mô tả UI | Vi sao: tài liệu API phải khớp hành vi thực tế.

Kết quả: 287 unit/API test pass; `node --check` và kiểm tra HTML pass; chưa chạy browser E2E.

## 2026-11-01 - Tải dữ liệu An Phú + HF legal foundation

- `backend/scripts/an_phu_fetch.py` — tải 52 văn bản/53 PDF, ghi manifest + checksum | Vi sao: cần dữ liệu local có nguồn gốc và retry.
- `.gitignore` — ignore `legal_hf/`, `an_phu/raw|pdf|text|ocr` | Vi sao: tránh commit ~864 MB dữ liệu tải về.
- `docs/PLAN_AN_PHU.md` — cập nhật 53 PDF, 7 text-layer, 46 scan | Vi sao: số liệu cũ 51 PDF sai do phụ lục.
- `backend/requirements.txt` — thêm `pyarrow==21.0.0` | Vi sao: đọc/filter parquet HF.

Kết quả: tải 53/53 PDF (92 MB) + HF 772 MB; 0 lỗi; 1 missing `id=2789`; verify parquet 171.556/170.824/1.033.255 rows, 732 metadata thiếu content; chưa OCR/ingest.

## 2026-11-01 - OCR 51 văn bản An Phú

- `backend/scripts/an_phu_prepare.py` — extract text-layer + OCR scan, checkpoint manifest, audit từng trang | Vi sao: 46 PDF scan cần text để ingest.
- `docs/PLAN_AN_PHU.md` — ghi kết quả OCR thực tế | Vi sao: plan cần phản ánh 375 trang và 1 trang lỗi.
- `backend/data/localities/an_phu/manifest.json` — cập nhật `ocr_status`, `page_count`, `char_count`, `text_path`, `quality_flag` | Vi sao: pipeline cần biết văn bản nào đã có text.

Kết quả: 51/52 văn bản có text; 375 trang (33 text-layer, 307 OCR, 34 blank); 563.997 ký tự; 1 trang lỗi `an_phu_2796` trang 23; 0 file rỗng.

## 2026-11-02 - Nhập text sửa tay An Phú + chuẩn hóa citation

- `backend/scripts/an_phu_import_text.py` — validate 51 file text, cập nhật manifest/summary | Vi sao: text người dùng sửa tay thay OCR nhưng manifest vẫn giữ số cũ.
- `backend/data/localities/an_phu/manifest.json` — `text_source=manual`, `ocr_status=done`, `char_count` thật, bỏ `quality_flag`, đánh dấu audit cũ stale | Vi sao: pipeline cần nguồn text và trạng thái đúng để ingest.
- `backend/data/localities/an_phu/text/an_phu_2454.txt` — sửa ngày ban hành `01/2/2025` thành `01/7/2025` | Vi sao: PDF trang 2 ghi thông qua ngày 01/7/2025, text cũ sai tháng.
- `backend/data/localities/an_phu/manifest.json` — sửa 10 số hiệu về đúng `TTHĐND/TT.HĐND` hoặc thêm năm; `an_phu_2837` tách ngày ký `31/7/2026` và ngày hiệu lực `29/7/2026` | Vi sao: citation phải khớp văn bản gốc, không dùng số hiệu rút gọn.
- `docs/PLAN_AN_PHU.md` — ghi trạng thái manual text, 658.860 ký tự; QA tự động pass, còn spot-check 8 văn bản | Vi sao: plan cần phản ánh dữ liệu thực tế trước Phase 4.

Kết quả: 51/51 file manual pass validate; 51 done + 1 missing (`an_phu_2789`); 658.860 ký tự; audit OCR cũ được giữ nhưng đánh dấu stale; chưa ingest/chunk; đã spot-check `an_phu_2454`, `an_phu_2837`, còn 8 văn bản.

## 2026-11-02 - Ingest 51 văn bản An Phú vào Chroma + BM25

- `backend/scripts/an_phu_ingest.py` — ingest text manual, metadata locality/citation, báo cáo, `--report-only` | Vi sao: Phase 7 cần đưa 51 văn bản vào Chroma/BM25.
- `backend/app/database/vector_store.py:89` — `add_chunks` nhận `extra_metadata` và merge vào từng chunk | Vi sao: citation/locality phải đi cùng chunk, không chỉ lưu document_id.
- `backend/app/rag/generation/llm_service.py:108` — prompt dùng `citation_label` làm trường `nguồn` | Vi sao: LLM trước đây chỉ thấy document_id nội bộ nên dễ trích dẫn sai.
- `backend/tests/unit/test_vector_store.py:161` — test metadata extra được lưu, bỏ value `None` | Vi sao: khóa contract metadata mới.
- `backend/tests/unit/test_llm_service.py:88` — test prompt chứa citation_label | Vi sao: tránh hồi quy citation về document_id.
- `.gitignore` — ignore `an_phu/ingest_report.json` | Vi sao: báo cáo sinh tự động, không commit.
- `docs/PLAN_AN_PHU.md` — ghi kết quả spot-check 10/10 + ingest 2.326 chunk, tổng 3.016 | Vi sao: plan phản ánh trạng thái Phase 3/7 thực tế.

Kết quả: 51 văn bản/2.326 chunk An Phú; Chroma + BM25 = 3.016 chunk; 4 query mẫu hit đúng văn bản; 288 unit/API test pass; re-ingest 1 văn bản không tăng count.

## 2026-11-02 - Phase 4: cấu trúc Điều/Khoản/Điểm + citation

- `backend/app/rag/ingestion/cleaner.py:62` — thêm `lowercase` để giữ case văn bản pháp lý | Vi sao: lowercase làm mất heading/trích dẫn.
- `backend/app/rag/ingestion/pipeline.py:189` — ingest gọi `clean(..., lowercase=False)`, fallback filename | Vi sao: giữ nguyên heading và chịu được loader mock.
- `backend/app/rag/ingestion/legal_structure.py:34` — parser `Điều/Khoản/Điểm`, annotate chunk | Vi sao: citation cần số Điều/Khoản/Điểm thay vì đoán từ prose.
- `backend/app/rag/ingestion/citation.py:38` — builder citation từ metadata, không URL | Vi sao: citation phải do hệ thống sinh, không để LLM bịa.
- `backend/app/models/data_models.py:56` — `Chunk.metadata` | Vi sao: mang metadata cấp chunk qua pipeline/vector store.
- `backend/app/database/vector_store.py:136` — merge `chunk.metadata` + extra metadata | Vi sao: `article_no`/`citation` phải vào Chroma.
- `backend/app/rag/generation/llm_service.py:108` — prompt ưu tiên `citation` của chunk | Vi sao: LLM thấy đúng số hiệu + Điều/Khoản/Điểm.
- `backend/scripts/an_phu_ingest.py:174` — annotate + gắn `citation` trước embed | Vi sao: re-ingest tạo metadata citation cho toàn bộ chunk.
- `backend/tests/unit/test_legal_structure.py` — test parser/annotate/citation | Vi sao: khóa hành vi regex và format citation.
- `backend/tests/integration/test_ingestion_pipeline.py` — sửa mock loader sync | Vi sao: test concurrent trước đây trả coroutine không await.

Kết quả: 277 Điều / 817 khoản / 363 điểm; 47/51 văn bản có ít nhất một Điều; 2.326 chunk An Phú có `citation`; Chroma/BM25 = 3.016; 310 test unit/API/ingestion pass; 690 chunk nền cũ vẫn lowercase.

## 2026-11-02 - Citation pháp lý inline, bỏ ID/file khỏi câu trả lời

- `backend/app/rag/generation/llm_service.py:31` — prompt chỉ dùng `NGUỒN PHÁP LÝ`, bỏ `document_id`/chunk/heading/Tài liệu N | Vi sao: LLM phải trích luật tự nhiên, không lộ mã nội bộ.
- `frontend/script.js:441` — xóa `addSources` và panel “Nguồn tham khảo” | Vi sao: chỉ hiển thị citation pháp lý trong câu trả lời.
- `frontend/style.css` — xóa CSS `.sources/.source-item/.source-doc/.source-snippet` | Vi sao: không còn UI nguồn tham khảo.
- `backend/tests/unit/test_llm_service.py:46` — cập nhật test prompt: có citation, không có ID/chunk/Tài liệu N | Vi sao: khóa hành vi citation mới.

Kết quả: E2E `Nghị quyết 24/NQ-HĐND` trả lời đúng dạng “Theo Nghị quyết số 24/NQ-HĐND ngày 31/7/2026 của HĐND phường An Phú, Điều 1…”, không có ID/file/chunk; 293 unit/API test pass; `node --check` pass.

## 2026-11-02 - Phase 4b: citation phụ lục + validator citation

- `backend/app/rag/ingestion/legal_structure.py:36` — nhận diện `PHỤ LỤC/DANH SÁCH/BIỂU/BẢNG/MẪU`, reset Điều/Khoản/Điểm | Vi sao: bảng phụ lục từng bị gắn sai `Điều 3`.
- `backend/app/rag/ingestion/legal_structure.py:85` — annotate `annex_title`, hỗ trợ heading Markdown `**Điều 1.**` | Vi sao: text manual có bold và bảng sau điều cuối.
- `backend/app/rag/ingestion/citation.py:13` — format citation phụ lục (`Biểu ...`, `Phụ lục ...`) | Vi sao: citation phải đúng loại tài liệu, không chỉ “Điều”.
- `backend/app/rag/generation/output_validator.py:246` — bắt buộc citation lấy từ metadata retrieve, chặn ID/file/chunk | Vi sao: LLM không được bịa số hiệu hoặc lộ mã nội bộ.
- `backend/app/rag/generation/output_validator.py:193` — evidence check tính cả citation metadata | Vi sao: answer có citation hợp lệ không bị đánh giá thiếu evidence.
- `backend/tests/unit/test_legal_structure.py:85` — test phụ lục reset Điều + citation | Vi sao: khóa hồi quy citation bảng.
- `backend/tests/unit/test_output_validator.py` — test citation đúng/thiếu/ID nội bộ | Vi sao: khóa validator mới.
- `docs/PLAN_AN_PHU.md` — cập nhật 280 Điều/820 khoản/363 điểm/43 phụ lục | Vi sao: plan khớp dữ liệu sau re-ingest.

Kết quả: 280 Điều / 820 khoản / 363 điểm / 43 phụ lục; 48/51 văn bản có Điều; 2.326 chunk An Phú không còn `annex_with_article`; Chroma/BM25 = 3.016; 298 unit/API test pass; E2E `24/NQ-HĐND` và `15/NQ-HĐND` trả citation đúng.

## 2026-11-03 - Ingest context An Phú + định tuyến profile/lịch/TTHC

- `backend/app/rag/retrieval/context_intent.py` — nhận diện profile/lịch/TTHC + tháng/năm | Vi sao: câu giờ làm việc/lịch từng trả sai loại tài liệu.
- `backend/app/rag/ingestion/procedure_metadata.py` — chuẩn hóa tên, citation, chấm điểm tên TTHC | Vi sao: citation lặp “Thủ tục Thủ tục” và biến thể “lưu động” thắng bản chuẩn.
- `backend/app/rag/retrieval/hybrid_retriever.py:180` — filter `$and`, lọc lịch theo tháng, rank tên TTHC, giới hạn 2 chunk/tài liệu | Vi sao: Chroma không nhận where nhiều khóa và context bị trùng tài liệu.
- `backend/scripts/an_phu_ingest_context.py:230` — dùng citation sạch + metadata `procedure_name` khi ingest | Vi sao: dữ liệu mới không tái phát lỗi citation.
- `backend/scripts/an_phu_patch_procedure_metadata.py` — patch metadata 5.524 chunk + rebuild BM25 | Vi sao: sửa dữ liệu cũ mà không embed lại 1.506 TTHC.
- `backend/tests/unit/test_context_intent.py` — test routing/lịch/tên TTHC/citation | Vi sao: khóa hồi quy các lỗi smoke test.
- `docs/PLAN_AN_PHU.md` — cập nhật 1.506 TTHC, 8.860 chunk, Phase 6/7/8 | Vi sao: plan còn số cũ 3.016 và chưa ingest context.

Kết quả: 1.506/1.506 TTHC; Chroma/BM25 8.860; 5.524 chunk TTHC có `procedure_name`, 0 citation lặp; 314 unit/API + 12 integration pass; smoke đúng profile, lịch 11/2025, TTHC khai sinh `1.001193`, không trả lịch khi hỏi 11/2026.

## 2026-11-03 - Evaluator locality + bộ 30 câu vàng An Phú

- `backend/app/rag/evaluation/evaluator.py` — thêm `locality_code`, relevance document-level, dedupe kết quả | Vi sao: bộ context có nhiều chunk/tài liệu và metric từng bị inflate.
- `backend/scripts/evaluate.py` — thêm `--locality-code`, truyền vào retrieval/answer eval | Vi sao: đánh giá phải giới hạn đúng An Phú.
- `backend/evaluation/an_phu_questions.jsonl` — 30 câu vàng (10 luật local, 10 TTHC, 5 lịch, 5 profile) | Vi sao: chưa có bộ đo riêng cho dữ liệu An Phú.
- `backend/evaluation/baselines/an_phu_retrieval.json` — baseline HitRate@5 1.00, MRR 0.881 | Vi sao: cần mốc hồi quy retrieval.
- `backend/evaluation/README.md` — hướng dẫn chạy bộ An Phú | Vi sao: dataset document-level khác bộ luật chunk-level.
- `backend/tests/unit/test_evaluation.py` — test locality/document-level/dedupe | Vi sao: khóa contract evaluator mới.
- `backend/app/rag/ingestion/procedure_metadata.py` — chấm điểm tên theo query coverage | Vi sao: TTHC “Hỗ trợ người cao tuổi...” bị thủ tục “Hỗ trợ sinh kế” lấn.
- `backend/app/rag/retrieval/hybrid_retriever.py:385` — quét title TTHC để bổ sung candidate long-tail | Vi sao: target nằm ngoài top 300 vector/BM25.
- `docs/PLAN_AN_PHU.md` — ghi baseline 30 câu và 318 test | Vi sao: plan cần trạng thái evaluation thực tế.

Kết quả: 30/30 câu hit@5 (document-level), HitRate@3 0.967, MRR 0.881; 318 unit/API + 12 integration pass; baseline lưu tại `backend/evaluation/baselines/an_phu_retrieval.json`.

## 2026-11-03 - Answer eval 30 câu An Phú + sửa lỗi TTHC

- `backend/app/rag/generation/llm_service.py:31` — prompt bắt buộc citation TTHC, strip UUID khỏi context | Vi sao: Gemini bỏ citation ở câu lệ phí/thời gian và lộ mã tiền tệ nội bộ.
- `backend/app/rag/retrieval/hybrid_retriever.py:360` — dedupe giữ chunk điểm cao, thêm fact chunk lệ phí/thời gian/hồ sơ | Vi sao: chunk đúng bị chunk trùng điểm thấp che mất.
- `backend/app/rag/retrieval/context_intent.py:26` — nhận diện “đăng ký thường trú” là TTHC | Vi sao: câu thường trú không được route sang procedure.
- `backend/tests/unit/test_context_intent.py:42` — test thường trú, dedupe điểm cao | Vi sao: khóa hồi quy routing/ranking.
- `backend/tests/unit/test_llm_service.py:109` — test strip UUID + rule citation TTHC | Vi sao: tránh lộ UUID và thiếu citation.
- `backend/evaluation/baselines/an_phu_answer_eval.json` — baseline answer 30 câu | Vi sao: cần mốc citation recall/term recall.
- `backend/evaluation/README.md` — ghi baseline answer | Vi sao: phân biệt source precision và answer citation.
- `docs/PLAN_AN_PHU.md` — ghi answer eval 30 câu, 321 test | Vi sao: cập nhật trạng thái Phase 10.

Kết quả: answer eval 30 câu đạt citation recall 1.00, expected term recall 0.944, abstention 0.033; 321 unit/API + 12 integration pass.

## 2026-11-04 - HF filter 10k + pilot 500 + hướng dẫn Colab

- `backend/scripts/hf_legal_filter.py` — lọc HCMC/trung ương còn hiệu lực, dedup, join content, clean HTML, xuất manifest/JSONL | Vi sao: Phase 5 cần corpus có kiểm toán trước khi embed.
- `backend/scripts/hf_legal_ingest.py` — ingest có checkpoint theo `document_id`, dry-run, report | Vi sao: 10k văn bản dễ đứt phiên, cần resume.
- `backend/app/rag/retrieval/hybrid_retriever.py:232` — exact doc-number lookup cả khi không có locality | Vi sao: câu hỏi luật toàn cục có số hiệu bị HF mới lấn.
- `docs/COLAB_HF_INGEST.md` — hướng dẫn zip/upload/copy/resume/rebuild/download trên T4 | Vi sao: embedding phần còn lại cần GPU và tránh I/O Drive.
- `docs/PLAN_AN_PHU.md` — ghi filter 10k, pilot 500, dự phóng T4 | Vi sao: plan cần số liệu đo thực tế.
- `backend/evaluation/baselines/an_phu_retrieval.json` — cập nhật baseline sau HF | Vi sao: MRR đổi từ 0.881 xuống 0.873.
- `backend/evaluation/README.md` — cập nhật baseline | Vi sao: số liệu phải khớp report.
- `backend/data/legal_hf/hf_ingest_report.json` — report pilot | Vi sao: lưu chunks/s và dự phóng 10k.

Kết quả: filter 10.000 văn bản (2.062 HCMC + 7.938 trung ương), 130,6M ký tự; pilot 500 = 15.089 chunk; Chroma/BM25 23.949; 4,24 chunk/s CPU, dự phóng 10k ~19,8 giờ CPU / 1–2 giờ T4; 30 câu An Phú HitRate@5 1.00; 50 câu luật cũ HitRate@5 0.38 sau pilot; 321 unit/API + 12 integration pass.

## 2026-11-04 - Ý kiến người dân + quản lý cho cán bộ + test UI

- `backend/app/models/db_models.py:47` — thêm bảng `feedback` | Vi sao: cần lưu phản ánh/góp ý và trạng thái xử lý.
- `backend/app/schemas/feedback.py` — schema create/list/update/status counts | Vi sao: khóa contract API và validate nội dung.
- `backend/app/api/feedback.py` — POST công khai, GET/PATCH cho cán bộ | Vi sao: dân gửi không cần đăng nhập, cán bộ xử lý có kiểm soát.
- `backend/app/api/admin.py:26` — thêm số ý kiến và ý kiến mới vào dashboard | Vi sao: cán bộ thấy việc cần tiếp nhận.
- `backend/app/main.py` — đăng ký router feedback; `scripts/init_db.py` tạo bảng | Vi sao: endpoint và DB phải sẵn sàng khi chạy.
- `frontend/index.html:45` — nút Góp ý + modal form công khai | Vi sao: người dân gửi ý kiến ngay trên UI chat.
- `frontend/admin.html:164` — màn hình “Ý kiến người dân” | Vi sao: cán bộ tiếp nhận, lọc, ghi chú, đổi trạng thái.
- `frontend/admin.js:703` — load/render/pagination/update feedback | Vi sao: luồng quản lý phải thao tác được không cần API thủ công.
- `frontend/style.css:602`, `frontend/admin.css:773` — style form/bảng/trạng thái | Vi sao: UI rõ ràng, responsive.
- `backend/tests/api/test_p1_api.py:380` — test public create + admin handling + 403 | Vi sao: chống hồi quy quyền và trạng thái.
- `docs/PLAN_AN_PHU.md:20` — hoãn full 10k HF + eval mở rộng cho AITeamVN | Vi sao: ưu tiên hiện tại là UI/feedback/cán bộ.
- `frontend/README.md` — cập nhật tính năng và API feedback | Vi sao: tài liệu UI phải khớp code.

Kết quả: 323 unit/API + 12 integration pass; Playwright UI flow pass (gửi ý kiến → đăng nhập cán bộ → mở admin → đổi trạng thái “Đang xử lý”).

## 2026-11-04 - Bỏ giới hạn 500 ký tự chat + CORS LAN

- `backend/app/api/chat.py:41` — bỏ `max_length=500` khỏi `QueryRequest` | Vi sao: UI/API chặn câu hỏi dài.
- `backend/app/rag/pipeline/hybrid_rag_pipeline.py:100` — bỏ check `MAX_QUERY_LENGTH` | Vi sao: pipeline vẫn từ chối câu >500 dù API đã cho phép.
- `frontend/script.js:567` — bỏ validate quá 500 ký tự | Vi sao: người dân phải nhập được câu hỏi dài.
- `frontend/index.html:73` — đổi hint còn tối thiểu 10 ký tự | Vi sao: không còn tuyên bố giới hạn 500.
- `backend/app/core/config.py:67` — thêm `cors_origin_regex` cho localhost/LAN private | Vi sao: OPTIONS chat bị 400 khi mở UI qua IP LAN.
- `backend/app/main.py:130` — truyền regex vào CORSMiddleware | Vi sao: trình duyệt gửi preflight từ `192.168.x.x`.
- `backend/tests/api/test_chat_api.py:197` — test câu 1200 ký tự trả 200 | Vi sao: khóa hành vi không giới hạn tối đa.
- `backend/tests/api/test_p1_api.py` — test CORS LAN private | Vi sao: tránh hồi quy 400 OPTIONS.
- `frontend/README.md` — cập nhật validate chat | Vi sao: tài liệu khớp UI.

Kết quả: chat nhận câu 1200 ký tự; CORS `192.168.1.10:3000` trả 200; 324 unit/API + 12 integration pass; Playwright gửi 1.349 ký tự lên API mock thành công.

## 2026-11-04 - Giảm latency chat + làm mượt câu trả lời

- `.env`, `.env.example`, `backend/app/core/config.py:19`, `backend/app/rag/generation/llm_service.py:30` — đổi model mặc định sang `gemini-3.1-flash-lite` | Vi sao: `gemini-3.5-flash-lite` đo được 12–19s/câu, 3.1-flash-lite phản hồi 1–4s.
- `backend/app/rag/generation/llm_service.py:39` — prompt trả lời trực tiếp, 2–5 câu, citation trong ngoặc | Vi sao: câu trả lời còn máy móc/“Theo…” lặp lại.
- `backend/app/api/chat.py:41` — bỏ max 500 ký tự | Vi sao: UI/API chặn câu hỏi dài.
- `backend/app/rag/pipeline/hybrid_rag_pipeline.py:100` — bỏ kiểm tra max length | Vi sao: pipeline vẫn từ chối câu >500.
- `frontend/script.js:567`, `frontend/index.html:73` — bỏ validate 500, hint tối thiểu 10 | Vi sao: người dân nhập câu dài.
- `backend/app/core/config.py:67`, `backend/app/main.py:130` — CORS regex localhost/LAN private | Vi sao: OPTIONS 400 khi mở UI qua IP LAN.
- `backend/tests/api/test_chat_api.py`, `backend/tests/api/test_p1_api.py` — test câu dài + CORS LAN | Vi sao: khóa hành vi mới.

Kết quả đo: retrieval 0,9s; LLM cũ 19,17s; model 3.1-flash-lite thường 2,2–3,7s (có spike API 36s). 324 unit/API pass; Playwright gửi câu 1.349 ký tự pass; CORS LAN pass.

## 2026-11-04 - Chặn chào hỏi bị chèn mã văn bản

- `backend/app/rag/generation/social_intent.py` — nhận diện chào hỏi/cảm ơn, trả welcome tĩnh | Vi sao: “xin chào” bị đưa qua RAG và LLM liệt kê mã văn bản.
- `backend/app/rag/pipeline/hybrid_rag_pipeline.py:195` — bypass retrieval/LLM cho social query | Vi sao: greeting không được lấy top chunk pháp lý.
- `backend/app/rag/generation/llm_service.py:50` — prompt cấm liệt kê tài liệu/mã khi chỉ chào hỏi | Vi sao: fallback vẫn giữ câu trả lời sạch.
- `backend/tests/unit/test_social_intent.py` — test welcome không mã, không gọi retriever/LLM | Vi sao: khóa hồi quy.
- `backend/tests/unit/test_llm_service.py:156` — live Gemini test thành opt-in `RUN_REAL_LLM_TESTS=1` | Vi sao: test suite không fail vì API timeout.

Kết quả: greeting trả welcome trong ~0,0001s, `source_chunks=[]`, không có mã; 325 unit/API pass + 3 skip; 12 integration pass.

## 2026-11-04 - Ẩn mã thủ tục khỏi câu trả lời

- `backend/app/rag/ingestion/procedure_metadata.py:25` — citation TTHC bỏ “mã …” | Vi sao: người dùng không muốn mã thủ tục trong câu trả lời.
- `backend/app/rag/generation/llm_service.py:31` — prompt strip dòng “Mã thủ tục:” | Vi sao: chặn LLM đọc/trích lại mã từ chunk text.
- `backend/app/rag/generation/llm_service.py:52` — instruction TTHC chỉ cite tên + Cổng DVC | Vi sao: giữ citation nhưng không lộ mã.
- `backend/scripts/an_phu_patch_procedure_metadata.py` — patch 5.524 chunk + rebuild BM25 | Vi sao: dữ liệu cũ vẫn chứa mã trong citation.
- `backend/evaluation/an_phu_questions.jsonl` — bỏ mã khỏi 10 expected citation TTHC | Vi sao: golden set khớp citation mới.
- `backend/tests/unit/test_context_intent.py:103`, `backend/tests/unit/test_llm_service.py` — test citation không mã + prompt strip | Vi sao: khóa hồi quy.

Kết quả: 5.524 chunk TTHC đã patch, 0 citation còn “mã 1.”; prompt không còn `Mã thủ tục:`; 325 unit/API + 3 skip + 12 integration pass.

## 2026-11-05 - Fix hồi quy retry/local intent

- `backend/app/rag/pipeline/hybrid_rag_pipeline.py:278` — retry truyền lại `locality_code` | Vi sao: retry k=10 trước đây tìm toàn cục, làm mất profile/local chunk.
- `backend/app/rag/pipeline/hybrid_rag_pipeline.py:318` — fallback ẩn lỗi kỹ thuật | Vi sao: UI từng hiện “Citation check failed…”.
- `backend/app/rag/retrieval/context_intent.py:26` — thêm “thời gian làm việc” là profile | Vi sao: câu hỏi giờ làm việc rơi vào lịch.
- `backend/app/rag/retrieval/hybrid_retriever.py:70` — boost chunk chứa “sáp nhập” | Vi sao: chunk NQ 19 xếp hạng 9, ngoài top 5.
- `backend/tests/unit/test_pipeline_resilience.py` — test retry giữ locality + fallback sạch | Vi sao: khóa hồi quy.
- `backend/tests/unit/test_context_intent.py` — test “thời gian làm việc” | Vi sao: khóa routing profile.

Kết quả: “thời gian làm việc” trả profile trong 1,43s; “sáp nhập” đưa NQ 19 lên top 1; câu không có dữ liệu trả fallback sạch trong 6,32s; 328 unit/API + 3 skip + 12 integration pass.

## 2026-11-06 - Bỏ validate 2 lớp + fallback LLM khi không truy xuất được

- `backend/app/rag/generation/llm_service.py:100` — bỏ validate/thay câu trả lời bằng fallback | Vi sao: pipeline từng validate câu placeholder nên câu trả lời thật bị loại oan (0.24 < 0.25).
- `backend/app/rag/generation/llm_service.py:32` — MODEL_NAME đọc từ settings | Vi sao: không có load_dotenv nên GEMINI_MODEL trong .env bị bỏ qua.
- `backend/app/rag/generation/llm_service.py:262` — thêm generate_answer_without_context | Vi sao: retrieval rỗng từng trả lời chết “Không tìm thấy tài liệu”.
- `backend/app/rag/generation/output_validator.py:47` — bỏ citation với câu “không tìm thấy thông tin” | Vi sao: câu trả lời đúng khi corpus thiếu dữ liệu bị fail Citation check.
- `backend/app/rag/generation/output_validator.py:142` — thêm validate_direct bỏ evidence/citation | Vi sao: câu không có context thì không thể có overlap hay số hiệu.
- `backend/app/rag/pipeline/hybrid_rag_pipeline.py:160` — fallback LLM trực tiếp khi retrieval lỗi/rỗng | Vi sao: yêu cầu vẫn trả lời được khi index không truy xuất được.
- `backend/tests/unit/test_pipeline_resilience.py:82` — test fallback rỗng/lỗi retrieval | Vi sao: khóa nhánh fallback mới.
- `backend/tests/unit/test_output_validator.py:72` — test câu từ chối + validate_direct | Vi sao: khóa bỏ citation oan.
- `backend/tests/unit/test_llm_service.py:331` — test text thật + prompt không context | Vi sao: khóa không nuốt câu trả lời.
- `backend/tests/integration/test_hybrid_rag_pipeline.py:476` — đổi kỳ vọng rỗng sang gọi LLM trực tiếp | Vi sao: hành vi rỗng đã đổi theo yêu cầu.

Kết quả: 434 test pass (2 fail có sẵn: thiếu module rank_bm25, test hardcode model); câu “sáp nhập tỉnh” và “thời gian làm việc” từng fail nay trả lời đúng; câu ngoài corpus trả LLM kèm disclaimer “(nguồn tổng quát, không có trong tài liệu của phường)”.

## 2026-11-06 - Đọc cấu hình từ .env + bỏ 2 test fail có sẵn

- `backend/app/core/config.py:17` — load_dotenv backend/.env trước khi tạo Settings | Vi sao: os.getenv từng không thấy GEMINI_MODEL nên phải hardcode tên model.
- `backend/app/rag/generation/llm_service.py:28` — model/max_tokens/temperature lấy từ settings | Vi sao: sửa .env không có tác dụng vì giá trị hardcode trong class.
- `backend/app/api/chat.py:115` — ví dụ OpenAPI dùng settings.gemini_model | Vi sao: docs còn hiển thị model `gemini-2.0-flash-exp` lỗi thời.
- `backend/app/rag/retrieval/bm25_index.py` — xóa module DEPRECATED dùng rank_bm25 | Vi sao: rank_bm25 không nằm requirements nên import là crash.
- `backend/tests/integration/test_enhanced_rag.py:61` — chuyển test sang BM25SIndex | Vi sao: test fail ModuleNotFoundError rank_bm25.
- `backend/tests/integration/test_rag_pipeline_real.py:63` — assert model theo settings | Vi sao: test hardcode `gemini-2.0-flash-exp` fail ở mọi môi trường.
- `backend/tests/test_gemini_api.py:17` — đọc .env theo đường dẫn tuyệt đối, bỏ mặc định 3.5 | Vi sao: script fail khi chạy từ thư mục khác và vẫn hardcode tên model.
- `backend/tests/unit/test_llm_service.py:39` — assert theo settings thay vì 500/0.3 | Vi sao: đổi .env làm test sai kỳ vọng cứng.

Kết quả: 436 test pass / 0 fail (trước đó 2 fail); `os.getenv("GEMINI_MODEL")` giờ trả `gemini-3.1-flash-lite` từ .env; server health 200.

## 2026-11-07 - Chốt Phase 10: sửa citation lịch làm việc, chặn URL, báo cáo eval

- `backend/app/rag/generation/output_validator.py:338` — `_check_citation` nhận thêm đuôi label sau dấu `:` (≥20 ký tự chuẩn hóa) | Vi sao: model trích "(Lịch làm việc HĐND - UBND ngày 12/01/2026 đến 17/01/2026)" thiếu tiền tố local nên q023–q025 fail 2 lần → refusal rỗng `source_chunks`, citation recall tụt xuống 0.9.
- `backend/app/rag/generation/output_validator.py:46` — thêm `URL_RE` chặn `http/www` trong answer | Vi sao: Phase 8 yêu cầu "Không có URL" nhưng validator chưa cài, chỉ API test mới phát hiện.
- `backend/app/rag/generation/output_validator.py:171` — `validate_direct` cũng chặn URL | Vi sao: câu fallback không có context vẫn có thể lộ link nguồn.
- `backend/tests/unit/test_output_validator.py:113` — 5 test mới (citation đuôi schedule, đuôi quá ngắn, 3 test URL) | Vi sao: khóa 2 hành vi validator mới.
- `backend/tests/unit/test_citation.py:1` — 8 test cho `citation_from_metadata`/`build_document_citation` | Vi sao: Phase 10 còn thiếu test citation_label builder (có/không số hiệu, có/không ngày, không URL).
- `.gitignore:97` — ignore `chroma_db.backup*/` và `bm25s_index.backup*/` | Vi sao: backup Phase 0 tạo lại hôm nay (605MB) từng là untracked, dễ commit nhầm vào git.
- `backend/docs/AN_PHU_EVAL.md:1` — báo cáo eval 30 câu + chẩn đoán q023–q025 + cách chạy lại | Vi sao: Phase 10 bắt buộc bàn giao báo cáo evaluation.
- `local-government-ai-assistant/docs/PLAN_AN_PHU.md` — tick Phase 0/1/2/4/6/8/10 + DoD + checklist bàn giao, ghi Phase 9 còn treo | Vi sao: checkbox stale dù việc đã xong, cần đúng trạng thái khi bàn giao.

Kết quả: eval 2026-11-07 — HitRate@5 1.00, MRR 0.873, citation recall 1.000, term recall 0.963, 0 câu rỗng nguồn, 0 URL (report `evaluation/results/an_phu_answer_eval_2026-11-07.json`); 477 test pass / 0 fail (trước 464); backup `chroma_db`/`bm25s_index` `.backup.2026-11-07` tạo lại và đã ignore.

## 2026-11-07 - Phase 9: 3 endpoint địa phương file-backed, source card 1 nguồn, strip URL

- `backend/app/services/locality_data.py:1` — đọc trực tiếp profile/schedules/manifest/procedures + cache + tìm `q` bỏ dấu | Vi sao: demo chốt file-backed nên không cần docker Postgres, và "ho tich" phải khớp được "hộ tịch".
- `backend/app/api/localities.py:1` — 3 GET public (profile/procedures/legal-documents) | Vi sao: plan §4.6 đòi endpoint tham chiếu nhưng dữ liệu demo vẫn nằm ở file.
- `backend/app/schemas/locality.py:1` — 10 response model không field URL | Vi sao: chặn `source_url/pdf_url/portal` ngay ở tầng schema thay vì tin từng handler.
- `backend/app/main.py:150` — đăng ký `localities_router` | Vi sao: thiếu include thì 3 endpoint không hiện ở `/docs` (điều kiện qua phase).
- `backend/app/models/data_models.py:16` — thêm `strip_urls()` | Vi sao: chunk profile chứa "Trang thông tin: https://phuonganphu.gov.vn" nên response chat thật lộ 1 URL.
- `backend/app/models/data_models.py:282` — `to_dict` strip URL + xuất `doc_type` | Vi sao: đây chính là chỗ URL lọt ra khi curl `/chat/query` thật.
- `backend/app/services/conversations.py:67` — `sources_payload` strip URL + `doc_type` | Vi sao: lịch sử chat lưu `text` cũng không được chứa link.
- `backend/frontend/script.js:542` — `buildSourceCard`: 1 nguồn `source_chunks[0]` với badge/citation/issuer | Vi sao: Phase 9 bắt buộc card hiển thị citation và không render URL.
- `backend/frontend/style.css:345` — CSS `.source-card/.source-badge/.source-citation/.source-meta` | Vi sao: card phải khớp theme `--primary/--line/--muted` hiện có.
- `backend/tests/api/test_locality_api.py:1` — 9 test (18 lịch, 1506/52 bản ghi, không-URL, q bỏ dấu, route đăng ký) | Vi sao: khóa điều kiện qua phase của Phase 9.
- `backend/tests/api/test_chat_api.py:62` — mock text có URL + assert `http` không trong response | Vi sao: chặn hồi quy portal URL lọt ra chat.
- `backend/tests/unit/test_sources_payload.py` + `test_data_models.py` + `test_llm_service.py` — mở rộng `doc_type`, +2 test strip URL | Vi sao: mọi tầng serialize phải cùng có doc_type và sạch URL.
- `docs/PLAN_AN_PHU.md` — tick Phase 9 (bảng DB + `legal_articles` ghi hoãn, demo file-backed) | Vi sao: checkbox còn treo dù việc đã xong đúng nghĩa.
