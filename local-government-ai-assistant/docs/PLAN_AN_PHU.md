# Kế hoạch triển khai dữ liệu Phường An Phú

## 0. Tóm tắt điều hành

Mục tiêu của kế hoạch này là đưa **Phường An Phú** trở thành địa phương pilot
đầu tiên của trợ lý ảo RAG, với ba lớp dữ liệu:

1. **Dữ liệu địa phương An Phú**: 52 văn bản pháp luật, 18 lịch làm việc,
   profile địa phương và dữ liệu thủ tục hành chính.
2. **Nền pháp lý TP.HCM + trung ương**: lọc từ Hugging Face dataset
   `th1nhng0/vietnamese-legal-documents`, không tự crawl lại toàn bộ
   `vbpl.vn`.
3. **Dữ liệu thủ tục hành chính**: lấy từ API DVC quốc gia, ưu tiên thủ tục
   cấp xã/phường và đối chiếu với địa bàn An Phú.

Kết quả cuối cùng là chatbot trả lời được câu hỏi về thủ tục, văn bản, lịch
làm việc và thông tin liên hệ của Phường An Phú; mỗi câu trả lời có citation
đúng số hiệu, ngày ban hành, cơ quan ban hành và Điều/Khoản/Điểm nếu có.
Citation hiển thị cho người dùng **không kèm URL**.

### 0.0. Ưu tiên hiện tại (2026-11-04)

- **Cập nhật 2026-11-07:** xong **toàn bộ Phase 0–10**, gồm Phase 9 (3 endpoint
  GET file-backed + source card 1 nguồn, không bảng DB — xem mục 4.6);
  answer eval 30 câu: `citation recall 1.000`, `term recall 0.963`,
  `HitRate@5 1.0`, 0 câu rỗng nguồn, 0 URL — báo cáo `backend/docs/AN_PHU_EVAL.md`.

- **Tạm hoãn full 10k HF + đánh giá truy xuất mở rộng**, để sau và phối hợp
  với **AITeamVN**. Hiện mới có manifest 10k + pilot 500; hướng dẫn Colab ở
  `docs/COLAB_HF_INGEST.md`.
- Ưu tiên hiện tại:
  1. [x] Test luồng UI chat/auth/admin ổn định.
  2. [x] Thêm chức năng **lấy ý kiến người dân**.
  3. [x] Thêm chức năng **quản lý cho cán bộ** (tiếp nhận/xử lý ý kiến, trạng thái,
     ghi chú nội bộ).
- Đã xong 2026-11-04: form góp ý công khai, API feedback, trang cán bộ
  “Ý kiến người dân”, Playwright UI flow pass; 324 unit/API + 12 integration.
- Đã bỏ giới hạn 500 ký tự chat; CORS mở cho localhost và LAN private
  (`192.168.x.x`, `10.x.x.x`, `172.16–31.x.x`).
- Chào hỏi/cảm ơn được trả lời tĩnh, không retrieval/LLM, không citation/mã.
- Citation TTHC không còn mã thủ tục; mã vẫn giữ trong metadata để tra cứu.
- Fix hồi quy: retry giữ `locality_code`, “thời gian làm việc” route profile,
  boost chunk “sáp nhập”, fallback không lộ lỗi validator.

### 0.1. Trạng thái thực hiện (2026-11-02)

- Đã tải HF dataset vào `backend/data/legal_hf/raw/`:
  - `data/metadata.parquet` — 15.143.095 bytes.
  - `data/content.parquet` — 784.578.084 bytes.
  - `data/relationships.parquet` — 9.436.116 bytes.
  - `README.md`, `CHANGELOG.md`; tổng ~772 MB.
  - Đã verify parquet: **171.556 metadata / 170.824 content / 1.033.255 relationships**;
    **732 metadata thiếu content**, 0 content mồ côi.
- Đã tải PDF An Phú vào `backend/data/localities/an_phu/pdf/`:
  - **52 văn bản**, **53 PDF**, **92 MB**, **0 lỗi tải**.
  - **7 PDF text-layer**, **46 PDF scan**, **1 missing PDF (`id=2789`)**.
  - 2 văn bản có 2 PDF (`id=2835`, `id=2836`); 1 văn bản có 3 JPG + 1 PDF (`id=2777`).
- Script tải: `backend/scripts/an_phu_fetch.py`.
- Manifest: `backend/data/localities/an_phu/manifest.json`.
- Đã OCR 51/52 văn bản có PDF (`an_phu_2789` không có PDF):
  - **375 trang**, **33 trang text-layer**, **307 trang OCR**, **34 trang blank**.
  - **563.997 ký tự**, 51 file text, 0 file rỗng.
  - **1 trang lỗi OCR**: `an_phu_2796` trang 23 (ảnh/bảng không đọc được).
  - Kết quả: `text/`, audit `ocr/*.pages.jsonl`, tổng hợp `ocr/summary.json`.
- **Đã thay text OCR bằng bản người dùng sửa tay** cho 51 văn bản:
  - 51/51 file UTF-8, không rỗng; tổng **658.860 ký tự**.
  - `manifest.json`: `text_source=manual`, `ocr_status=done`, `failed_pages=0`,
    `pages_audit_stale=true`; audit OCR cũ chỉ giữ tham chiếu.
  - Đã sửa metadata citation: 10 số hiệu giữ đúng `TTHĐND/TT.HĐND` hoặc năm;
    `an_phu_2454` sửa ngày `01/7/2025`; `an_phu_2837` tách ngày ký `31/7/2026`
    và ngày hiệu lực `29/7/2026`.
  - Script kiểm tra/cập nhật: `backend/scripts/an_phu_import_text.py`.
- Đã spot-check **10/10 văn bản** (8 mới + `an_phu_2454`, `an_phu_2837`):
  - 10/10 khớp số hiệu/ngày/title ở mức header; 5 trích đoạn prose đối chiếu PDF.
  - Bảng giữ cấu trúc `|`; chưa đối chiếu từng ô số liệu.
- **Đã ingest 51 văn bản An Phú** vào Chroma + BM25:
  - **2.326 chunk An Phú**; tổng collection **3.016 chunk** (690 nền + 2.326 local).
  - BM25S corpus **3.016**; metadata có `locality_code`, `locality_slug`,
    `doc_number`, `issued_date`, `citation_label`, `text_source=manual`.
  - Re-ingest `an_phu_2454` không tăng chunk count (idempotent).
  - Script: `backend/scripts/an_phu_ingest.py`; báo cáo: `ingest_report.json`.
- **Phase 4/4b đã xong cho An Phú**:
  - `TextCleaner` có `lowercase`; pipeline giữ case khi ingest.
  - `legal_structure.py` tách **280 Điều / 820 khoản / 363 điểm / 43 phụ lục**;
    48/51 văn bản có ít nhất một `Điều`.
  - Chunk phụ lục/bảng không còn bị gắn sai `Điều` cuối; citation dạng
    `..., Biểu ...` hoặc `..., Phụ lục ...`.
  - Mỗi chunk có `article_no`, `clause_no`, `point_no`, `annex_title`, `citation`.
  - `OutputValidator` chặn answer thiếu citation, chứa `document_id`/`chunk`/
    `an_phu_*`/tên file.
  - Đã re-ingest 51 văn bản; Chroma/BM25 vẫn **3.016 chunk**.
- **Phase 6/7 đã xong dữ liệu context**:
  - 1.506 TTHC cấp xã, 0 trùng `procedure_id`, detail 100%; 18 lịch + profile.
  - Chroma/BM25 **8.860 chunk** (3.083 luật + 252 lịch + 1 profile + 5.524 TTHC).
  - Retrieval routing profile/lịch/TTHC, lọc tháng/năm, xếp hạng tên TTHC chuẩn.
  - Bộ 30 câu vàng An Phú: `HitRate@5 = 1.00`, `MRR = 0.881`; baseline
    `evaluation/baselines/an_phu_retrieval.json`.
  - Answer eval 30 câu (Gemini): citation recall 1.00, term recall 0.944,
    abstention 0.033; baseline `evaluation/baselines/an_phu_answer_eval.json`.
  - 321 unit/API test pass; 12 integration retrieval/pipeline pass.
- **HF Phase 5 mới xong filter + pilot 500**:
  - Filter còn hiệu lực: 10.000 văn bản (2.062 HCMC + 7.938 trung ương), 130,6M ký tự.
  - Pilot 500: 15.089 chunk; Chroma/BM25 **23.949 chunk**; 4,24 chunk/s CPU.
  - Dự phóng 10k: ~301.780 chunk, ~19,8 giờ CPU; T4 dự kiến 1–2 giờ.
  - 30 câu An Phú vẫn HitRate@5 1.00; 50 câu luật cũ HitRate@5 0.38 sau pilot
    (chưa kết luận vì mới 500/10k).

---

## 1. Mục tiêu, phạm vi và Definition of Done

### 1.1. Mục tiêu

- Xây dựng corpus An Phú có nguồn gốc rõ ràng, có manifest và checksum.
- OCR toàn bộ PDF scan của An Phú ngay trong giai đoạn chuẩn bị dữ liệu.
- Chuẩn hóa metadata để retrieval lọc được theo địa phương, loại văn bản,
  hiệu lực và phạm vi áp dụng.
- Sinh citation từ metadata của chunk, không để LLM tự bịa nguồn.
- Giữ pipeline hiện tại: FastAPI + ChromaDB + BM25S + Gemini.
- Không phá vỡ chức năng auth, conversation, admin hiện có.

### 1.2. Trong phạm vi

- Một địa phương duy nhất: **Phường An Phú**, mã dự kiến `25975`.
- Văn bản do HĐND/UBND Phường An Phú ban hành.
- Văn bản TP.HCM và trung ương có liên quan đến lĩnh vực hành chính cấp cơ sở.
- Thủ tục hành chính cấp xã/phường từ DVC quốc gia.
- Lịch làm việc, tiếp công dân, thông tin liên hệ, giờ làm việc.
- Chat API và màn hình chat hiện tại; chưa làm lại frontend.

### 1.3. Ngoài phạm vi

- Không tự crawl lại toàn bộ `vbpl.vn`.
- Không tìm văn bản cấp phường/xã từ `vbpl.vn` vì nguồn này không có.
- Không nộp hồ sơ, thanh toán, ký số hoặc thay người dân thực hiện thủ tục.
- Không huấn luyện/fine-tune mô hình.
- Không hỗ trợ nhiều phường/xã trong cùng một phiên bản pilot.
- Không đưa URL vào câu trả lời/citation hiển thị cho người dùng.

### 1.4. Definition of Done

- [x] Manifest An Phú có đủ **52 văn bản**.
- [x] Có **53 PDF** tải thành công; **1 văn bản `id=2789`** được đánh dấu
      `missing_pdf` và không bị coi là có toàn văn.
- [x] **46 PDF scan** được OCR; **7 PDF text-layer** được trích xuất trực tiếp.
- [x] Ghi rõ 2 văn bản có 2 PDF (`an_phu_2835`, `an_phu_2836`) và 1 văn bản
      (`an_phu_2777`) có 3 JPG + 1 PDF.
- [x] **18 lịch làm việc** trong `schedules.json` + thông tin liên hệ xác minh
      trong `profile.yaml` (khối `verification`: ward 25975/UUID).
- [x] Có dữ liệu TTHC cấp xã/phường; API không hỗ trợ lọc theo An Phú →
      ghi rõ fallback toàn quốc 1.506 TTHC + `applies_to_an_phu=true`.
- [x] Corpus HF được lọc theo TP.HCM + trung ương + còn hiệu lực;
      log rõ số lượng trước/sau lọc (`hf_manifest.json`: 171.556 → 10.000).
- [x] Chat trả lời đúng citation cho ít nhất **20/30 câu hỏi vàng** (đạt 30/30).
- [x] Không có citation chứa URL; không có citation bịa số hiệu
      (validator chặn URL/số hiệu ngoài context; eval 0 URL, 0 refusal).
- [x] `pytest tests/unit tests/api -q` pass; integration test An Phú có marker riêng.
- [x] Có thể chạy lại toàn bộ pipeline mà không tạo chunk trùng.

---

## 2. Nguồn dữ liệu và số liệu đã xác minh

### 2.1. Bảng nguồn

| Nguồn | Vai trò | Số lượng | Trạng thái | Cách dùng |
|---|---|---:|---|---|
| `https://phuonganphu.gov.vn` | Cổng phường An Phú | 1 tenant `523` | Đã kiểm tra | Nguồn chính thức cho văn bản/lịch/profile |
| `/api/legal-document?page=1..2` | API metadata văn bản local | 52 | Đã kiểm tra | Đối chiếu; API không trả attachments |
| `/van-ban-phap-luat?page=1..6` | Nuxt payload có PDF URL | 52 docs / 53 PDF | Đã kiểm tra | Nguồn tạo manifest + tải PDF |
| CDN `government.cdn.myaloha.com.vn/tenant523` | PDF đính kèm | 53 PDF | 7 text-layer, 46 scan, 1 missing | Tải về, checksum, OCR |
| `/lich-lam-viec` | Lịch làm việc | 18 | Đã kiểm tra | Parse thành `schedules.json` |
| Trang giới thiệu/liên hệ | Profile địa phương | 1 | Đã kiểm tra | Viết tay/chuẩn hóa vào `profile.yaml` |
| DVC quốc gia | TTHC cấp xã | 1.506 thủ tục `COMMUNE` | Đã kiểm tra API | Lấy list + detail, cache JSON |
| HF `th1nhng0/vietnamese-legal-documents` | Nền pháp lý | 171.556 metadata / 170.824 content | Snapshot `2026-07-23` | Lọc, join, ingest |
| `vbpl.vn` | Đối chiếu văn bản TP.HCM/trung ương | 11.982 văn bản TP.HCM | Đã kiểm tra | Chỉ dùng để xác minh, không crawl toàn bộ |

### 2.2. Đặc điểm dữ liệu An Phú

- API văn bản trả **52 văn bản**, tất cả là văn bản của HĐND/UBND Phường An Phú,
  không phải văn bản trung ương.
- `content` trong API chỉ là tiêu đề/trích yếu, **không phải toàn văn**.
- Toàn văn nằm trong PDF tại CDN.
- Phân loại PDF (đã audit sau khi tải):
  - **53 PDF đính kèm** cho 51/52 văn bản; 2 văn bản có 2 PDF do kèm phụ lục.
  - **7 PDF có text layer**: trích xuất trực tiếp.
  - **46 PDF scan**: bắt buộc OCR.
  - **1 văn bản không có PDF (`id=2789`)**: chỉ dùng metadata/trích yếu.
  - **1 văn bản (`id=2777`) có 3 JPG + 1 PDF**: chỉ tải PDF, ghi metadata JPG.
- Hai PDF từng lỗi tải tạm thời: `id=2459`, `id=2835`; phải retry và ghi log.
- Trang `/thu-tuc-hanh-chinh` chưa có dữ liệu; không scrape trang này.
- Trang `/lich-lam-viec` có **18 lịch làm việc**.
- Thông tin liên hệ:
  - Địa chỉ: `Số 9, đường ĐT 743, khu phố 1A, TP.HCM`.
  - Điện thoại: `02743 740021`.
  - Email: `anphu@tphcm.gov.vn`.
- Mã phường: `25975` lấy từ nguồn tổng hợp; **phải xác minh lại** qua DVC/LGSP
  trước khi ghi vào DB chính thức.

### 2.3. Đặc điểm HF dataset

- Dataset: `th1nhng0/vietnamese-legal-documents`.
- License: CC BY 4.0.
- Snapshot: `2026-07-23`.
- Current configs:
  - `metadata`: 171.556 dòng.
  - `content`: 170.824 dòng.
  - `relationships`: 1.033.255 dòng.
- Kích thước parquet hiện tại:
  - `metadata.parquet` ~15 MB.
  - `content.parquet` ~784 MB.
  - `relationships.parquet` ~9 MB.
  - Tổng dataset ~4,37 GB.
- Join key:
  - `metadata.id` ↔ `content.id`.
  - `metadata.id` ↔ `relationships.doc_id`.
- `id` là string, không phải integer.
- **732 metadata rows không có content**; phải drop và log.
- Chỉ dùng current configs, không dùng legacy config mặc định.

### 2.4. Đặc điểm DVC API

- List TTHC:
  `POST https://dichvucong.gov.vn/api/v1/submitting/formality/list-all-public-formality-by-citizen`
- Detail TTHC:
  `POST https://dichvucong.gov.vn/api/v1/configuring/formality/get-formality-by-citizen`
  body `{"id":"<UUID>"}`.
- Ward/province:
  `POST https://dichvucong.gov.vn/api/v1/configuring/ward/list-by-citizen`
  body `{"provinceCode":"79","limit":300,"lastId":""}`.
- Bắt buộc:
  - `Content-Type: application/json; charset=UTF-8`.
  - `Accept: application/json`.
  - `Origin: https://dichvucong.gov.vn`.
  - `Referer: https://dichvucong.gov.vn/`.
- Success trả HTTP **201**, không phải 200.
- `limit` tối đa **200**.
- Có rate limit/connection chập chờn; dùng retry + backoff.
- `level:"COMMUNE"` trả **1.506** thủ tục cấp xã.
- `q:"khai sinh"` + `level:"COMMUNE"` trả **13**.
- `provinceCode:"79"&wardCode:"26740"` trả **57** thủ tục đặc thù Sài Gòn;
  thêm `level:"COMMUNE"` còn **22**.
- Thủ tục mẫu:
  - Đăng ký khai sinh: code `1.001193`,
    UUID `019d2bfd-3fe0-70ac-b9d6-5e9e20d6eef7`.
  - Cấp bản sao trích lục hộ tịch: code `2.000635`,
    UUID `019d2bfd-867c-72db-b6a7-dcbd8c763807`.

---

## 3. Quyết định thiết kế

### 3.1. Nguồn nào là source of truth?

| Dữ liệu | Source of truth | Dữ liệu phái sinh |
|---|---|---|
| Văn bản An Phú | `manifest.json` + PDF gốc + text đã OCR | Chroma chunk, BM25S index |
| Lịch/profile An Phú | `profile.yaml` + `schedules.json` | Chroma chunk |
| TTHC | `procedures.jsonl` + raw JSON | Chroma chunk |
| Văn bản TP.HCM/trung ương | HF parquet đã lọc + manifest phụ | Chroma chunk |
| Citation | Metadata của chunk | Không sinh từ LLM |

Không lấy Chroma làm nguồn duy nhất cho metadata pháp lý. Chroma là index;
manifest/DB là nguồn kiểm toán.

### 3.2. Nguyên tắc citation

- Citation lấy từ `citation_label` đã chuẩn hóa trong metadata.
- Không cho LLM tự tạo số hiệu hoặc ngày ban hành.
- Văn bản local:
  `[Nghị quyết số 25/NQ-HĐND ngày 29/7/2026 của HĐND phường An Phú, Điều 3, khoản 2]`
- Văn bản không có số hiệu:
  `[Thông báo của UBND phường An Phú ngày 29/6/2026 về sắp xếp khu phố]`
- TTHC:
  `[Thủ tục đăng ký khai sinh, mã 1.001193, Cổng DVC quốc gia]`
- Lịch:
  `[Lịch làm việc UBND phường An Phú ngày 29/7/2026]`
- Không hiển thị URL trong citation hoặc câu trả lời.

### 3.3. Nguyên tắc chunking

- Giữ nguyên chữ hoa/thường của văn bản gốc để bảo toàn số hiệu, tên riêng,
  tiêu đề Điều/Khoản.
- Không lowercase toàn bộ văn bản trước khi lưu Chroma.
- BM25 vẫn lowercase token khi index; embedding dùng văn bản gốc.
- Chunk ưu tiên theo Điều/Khoản/Điểm; fallback paragraph.
- Mỗi chunk phải có `article_no`, `clause_no`, `point_no` nếu nhận diện được.
- Không tách một Điều quá dài thành chunk mất ngữ cảnh; giữ heading context.

### 3.4. Nguyên tắc retrieval

- Local-first:
  1. Tìm trong `locality_code=25975`.
  2. Nếu thiếu kết quả hoặc điểm thấp, fallback sang `doc_scope in [hcmc, central]`.
- Không trộn local và global ngay từ đầu để tránh văn bản trung ương lấn át
  văn bản phường.
- Với câu hỏi TTHC, ưu tiên `doc_scope=procedure`.
- Với câu hỏi lịch/profile, ưu tiên `doc_scope in [schedule, profile]`.
- Có thể dùng query classifier nhẹ bằng keyword trước; chưa cần model riêng.

---

## 4. Cấu trúc thư mục và hợp đồng dữ liệu

### 4.1. Cấu trúc thư mục

```text
local-government-ai-assistant/backend/data/
├── localities/
│   └── an_phu/
│       ├── profile.yaml
│       ├── manifest.json
│       ├── schedules.json
│       ├── procedures.jsonl
│       ├── pdf/
│       │   ├── an_phu_2459.pdf
│       │   └── ...
│       ├── text/
│       │   ├── an_phu_2459.txt
│       │   └── ...
│       └── ocr/
│           ├── an_phu_2459.pages.jsonl
│           └── ...
└── legal_hf/
    ├── filtered_metadata.parquet
    ├── filtered_content.parquet
    └── hf_manifest.json
```

### 4.2. `manifest.json`

Mỗi văn bản local có một entry. `doc_id` ổn định theo portal id:
`an_phu_<portal_id>`.

```json
{
  "locality": {
    "code": "25975",
    "name": "Phường An Phú",
    "parent": "TP.HCM",
    "portal": "https://phuonganphu.gov.vn"
  },
  "generated_at": "2026-10-31T00:00:00+07:00",
  "source_api": "https://phuonganphu.gov.vn/api/legal-document",
  "documents": [
    {
      "doc_id": "an_phu_2788",
      "portal_id": 2788,
      "title": "Quy chế tiếp công dân của HĐND phường An Phú",
      "doc_number": "25/NQ-HĐND",
      "doc_type": "Nghị quyết",
      "issuer": "HĐND phường An Phú",
      "issued_date": "2026-07-29",
      "effective_date": null,
      "source_url": "https://phuonganphu.gov.vn/...",
      "pdf_url": "https://government.cdn.myaloha.com.vn/tenant523/attachments/...pdf",
      "pdf_path": "pdf/an_phu_2788.pdf",
      "pdf_sha256": "...",
      "text_path": "text/an_phu_2788.txt",
      "ocr_status": "ocr",
      "page_count": 4,
      "char_count": 8123,
      "citation_label": "Nghị quyết số 25/NQ-HĐND ngày 29/7/2026 của HĐND phường An Phú",
      "notes": ""
    }
  ]
}
```

`ocr_status` chỉ nhận một trong các giá trị:

- `text_layer`: PDF có text layer, không cần OCR.
- `ocr`: PDF scan đã OCR thành công.
- `missing_pdf`: không có PDF, chỉ có metadata/trích yếu.
- `failed`: tải/OCR lỗi, cần xử lý thủ công.

### 4.3. `profile.yaml`

```yaml
locality:
  code: "25975"
  name: "Phường An Phú"
  level: "phuong"
  parent: "TP.HCM"
  portal: "https://phuonganphu.gov.vn"

contact:
  address: "Số 9, đường ĐT 743, khu phố 1A, TP.HCM"
  phone: "02743 740021"
  email: "anphu@tphcm.gov.vn"

working_hours:
  weekdays: "07:30-11:30, 13:30-17:00"
  saturday: "07:30-11:30"
  sunday: "Nghỉ"

schedules:
  - date: "2026-07-29"
    time: "08:00"
    location: "Hội trường UBND phường An Phú"
    chair: "..."
    content: "..."
    participants: "..."
    source_url: "https://phuonganphu.gov.vn/lich-lam-viec/..."
```

### 4.4. `procedures.jsonl`

Mỗi dòng là một thủ tục đã chuẩn hóa:

```json
{
  "procedure_id": "1.001193",
  "uuid": "019d2bfd-3fe0-70ac-b9d6-5e9e20d6eef7",
  "name": "Đăng ký khai sinh",
  "level": "COMMUNE",
  "locality_code": "25975",
  "agency": "UBND phường An Phú",
  "description": "...",
  "required_documents": [],
  "processing_time": "01 ngày",
  "fee": "0 đồng",
  "legal_basis": [],
  "source_url": "https://dichvucong.gov.vn/...",
  "raw_json_path": "raw/procedures/1.001193.json"
}
```

### 4.5. Metadata chunk trong ChromaDB

Chroma chỉ nhận metadata scalar. Tất cả giá trị phải là `str`, `int`, `float`
hoặc `bool`; không dùng `None`.

```json
{
  "document_id": "an_phu_2788",
  "chunk_index": 3,
  "locality_code": "25975",
  "locality_name": "Phường An Phú",
  "doc_scope": "local",
  "doc_type": "Nghị quyết",
  "doc_number": "25/NQ-HĐND",
  "issued_date": "2026-07-29",
  "effective_date": "",
  "issuer": "HĐND phường An Phú",
  "legal_status": "Còn hiệu lực",
  "article_no": "Điều 3",
  "clause_no": "2",
  "point_no": "",
  "citation_label": "Nghị quyết số 25/NQ-HĐND ngày 29/7/2026 của HĐND phường An Phú",
  "source_url": "https://phuonganphu.gov.vn/...",
  "filename": "an_phu_2788.pdf",
  "heading_context": "Điều 3. Quyền và nghĩa vụ của công dân"
}
```

`doc_scope` chỉ nhận:

- `local`: văn bản phường An Phú.
- `hcmc`: văn bản TP.HCM.
- `central`: văn bản trung ương.
- `procedure`: thủ tục hành chính.
- `profile`: profile địa phương.
- `schedule`: lịch làm việc.

### 4.6. Bảng PostgreSQL dự kiến

Giữ nguyên `users`, `conversations`, `messages`. Thêm:

| Bảng | Cột chính | Mục đích |
|---|---|---|
| `localities` | `id`, `code`, `name`, `level`, `parent_code`, `portal_url`, `address`, `phone`, `email`, `source_url` | Danh mục địa phương |
| `locality_profiles` | `id`, `locality_id`, `profile_json`, `version`, `updated_at` | Profile/lịch dạng JSON có version |
| `legal_documents` | `id`, `doc_id`, `locality_code`, `doc_scope`, `title`, `doc_number`, `doc_type`, `issuer`, `issued_date`, `effective_date`, `legal_status`, `source_url`, `pdf_url`, `pdf_sha256`, `text_path`, `ocr_status`, `metadata_json` | Metadata văn bản |
| `legal_articles` | `id`, `document_id`, `article_no`, `clause_no`, `point_no`, `heading`, `content`, `order_index` | Cấu trúc Điều/Khoản/Điểm |
| `procedures` | `id`, `procedure_id`, `uuid`, `name`, `level`, `locality_code`, `agency`, `description`, `required_documents_json`, `processing_time`, `fee`, `legal_basis_json`, `source_url`, `raw_json` | TTHC |
| `ingestion_runs` | `id`, `source`, `started_at`, `finished_at`, `status`, `stats_json` | Audit mỗi lần ingest |

Index tối thiểu:

- `legal_documents(locality_code)`.
- `legal_documents(doc_scope)`.
- `legal_documents(doc_number)`.
- `legal_documents(legal_status)`.
- `procedures(procedure_id)` unique.
- `procedures(locality_code)`.

---

## 5. Kiến trúc pipeline đích

```text
An Phú portal API
      │
      ├── 52 metadata ──► manifest.json
      ├── 53 PDF ───────► pdf/ ──► extract/OCR ──► text/
      ├── 18 lịch ──────► schedules.json
      └── profile ──────► profile.yaml
                              │
DVC API ──► procedures.jsonl ─┤
                              ├──► ingest ──► ChromaDB
HF parquet ──► filter/join ───┘              └──► BM25S
                                                   │
                                            Hybrid retrieval
                                                   │
                                            Citation builder
                                                   │
                                            Chat API / UI
```

---

## 6. Kế hoạch theo phase

### Phase 0 — Preflight và xác minh địa phương (0,5 ngày)

**Việc cần làm**

- [x] Xác minh `25975` là mã Phường An Phú qua DVC ward API và portal.
- [x] Ghi lại `provinceCode=79`, `wardCode=25975`, `ward_id`/UUID nếu có
      (UUID `019bad30-cd8e-7296-afa4-f836804d385b`, ghi trong `profile.yaml`).
- [x] Kiểm tra `tesseract --list-langs` có `vie`
      (đã OCR 307 trang tiếng Việt 02/11; cài lại bằng
      `backend/scripts/setup_tesseract_local.sh` nếu mất binary).
- [x] Kiểm tra dung lượng ổ đĩa: cần tối thiểu 8 GB trống cho HF + PDF + Chroma.
- [x] Backup `chroma_db/` và `bm25s_index/` trước khi ingest
      (đã tạo lại `*.backup.2026-11-07` = 511M + 94M, thêm vào `.gitignore`).
- [x] Tạo `.env` local với `GEMINI_API_KEY`, `DATABASE_URL`.
- [x] Chạy baseline `pytest tests/unit tests/api -q`.

**Lệnh**

```bash
cd local-government-ai-assistant/backend
source .venv/bin/activate
tesseract --list-langs | grep vie
cp -a chroma_db "chroma_db.backup.$(date +%F)"
cp -a bm25s_index "bm25s_index.backup.$(date +%F)"
python -m pytest tests/unit tests/api -q
```

**Đầu ra**

- `profile.yaml` có mã địa phương đã xác minh.
- Ghi chú xác minh trong `manifest.json` hoặc `docs/PLAN_AN_PHU.md` phần phụ lục.

**Điều kiện qua phase**

- `25975` khớp tên Phường An Phú.
- OCR `vie` sẵn sàng.
- Baseline test pass.

---

### Phase 1 — Snapshot portal và tạo manifest (0,5 ngày)

**Việc cần làm**

- [x] Gọi API `/api/legal-document?page=1..2`, lưu raw JSON.
- [x] Parse 52 văn bản, chuẩn hóa `title`, `doc_number`, `doc_type`, `issuer`,
      `issued_date`, `source_url`, `pdf_url`.
- [x] Tải trang `/lich-lam-viec`, lưu HTML, parse 18 lịch (`schedules.json`).
- [x] Tải trang giới thiệu/liên hệ, đối chiếu `profile.yaml`.
- [x] Tạo `manifest.json` với `doc_id = an_phu_<portal_id>` (52 entry, 0 trùng).
- [x] Đánh dấu `id=2789` là `missing_pdf`.
- [x] Kiểm tra không có `doc_id` trùng (`test_manifest.py` + validator thật).

**File dự kiến**

- `backend/scripts/an_phu_fetch.py` (mới).
- `backend/app/rag/ingestion/manifest.py` (mới, loader/validator).
- `backend/data/localities/an_phu/manifest.json`.
- `backend/data/localities/an_phu/profile.yaml`.
- `backend/data/localities/an_phu/schedules.json`.

**Điều kiện qua phase**

- 52 entry, 1 entry `missing_pdf`, 51 entry có ít nhất 1 `pdf_url`, tổng 53 PDF attachment.
- 18 lịch có `date`, `time`, `content`.
- 0 `doc_id` trùng; 0 ngày sai format.

---

### Phase 2 — Tải PDF, checksum và retry (0,5 ngày)

**Việc cần làm**

- [x] Tải 53 PDF từ CDN, ghi checksum `sha256` (53/53 attachment).
- [x] Retry các ID `2459`, `2835` với backoff.
- [x] Kiểm tra magic bytes `%PDF-` và `Content-Type: application/pdf`.
- [x] Bỏ file `.part` nếu lỗi; không ghi đè PDF đã có checksum hợp lệ.
- [x] Ghi log tải: `downloaded`, `skipped`, `failed` (0 failed).

**Quy tắc**

- Concurrency tối đa 2.
- Sleep 0,5–1 giây giữa các request.
- Retry 3 lần, backoff 2/4/8 giây.
- Không coi HTML lỗi là PDF.

**Điều kiện qua phase**

- 53 PDF hợp lệ; 1 missing đúng `id=2789`.
- 0 file 0 byte; 0 file HTML giả PDF.
- Checksum ổn định khi chạy lại.

---

### Phase 3 — Extract text và OCR toàn bộ PDF scan (1–1,5 ngày)

**Việc cần làm**

- [x] Dùng `DocumentLoader` hiện có với:
      `ocr_enabled=True`, `ocr_lang=vie`, `ocr_dpi=400`,
      `ocr_min_chars_per_page=50`.
- [x] Với 7 PDF text-layer: trích xuất trực tiếp.
- [x] Với 46 PDF scan: OCR toàn bộ trang.
- [x] Ghi text vào `text/an_phu_<id>.txt`.
- [x] Ghi thống kê từng trang vào `ocr/an_phu_<id>.pages.jsonl`.
- [x] Cập nhật `ocr_status`, `page_count`, `char_count` vào manifest.
- [x] Nếu OCR một trang lỗi: đánh dấu `failed`, không âm thầm bỏ trang.
- [x] Thay text OCR bằng bản người dùng sửa tay; cập nhật manifest qua
      `backend/scripts/an_phu_import_text.py`.

**QA bắt buộc**

- [x] Không có file text rỗng.
- [x] Không có văn bản < 200 ký tự sau OCR (trừ văn bản quá ngắn có lý do).
- [x] Kiểm tra thủ công 10 văn bản, gồm:
  - `25/NQ-HĐND` Quy chế tiếp công dân.
  - `231/TB-UBND` sắp xếp khu phố.
  - 1 văn bản ngân sách.
  - 1 văn bản có bảng biểu.
  - 6 văn bản scan ngẫu nhiên.
  - Đã spot-check 10/10: `an_phu_2454`, `an_phu_2777`, `an_phu_2786`,
    `an_phu_2793`, `an_phu_2796`, `an_phu_2809`, `an_phu_2466`,
    `an_phu_2813`, `an_phu_2837`, `an_phu_2838`.
- [x] So sánh ít nhất 5 trích đoạn OCR với ảnh PDF gốc.
- [x] Kiểm tra 51 file manual: UTF-8, không rỗng, không lỗi OCR phổ biến;
      giữ bảng bằng dấu `|`.

**Điều kiện qua phase**

- 46/46 PDF scan có text.
- 7/7 PDF text-layer có text.
- 1/1 missing được đánh dấu, không có text giả.
- 10/10 văn bản spot-check đạt.

---

### Phase 4 — Chuẩn hóa, cấu trúc Điều/Khoản và citation (1 ngày)

**Việc cần làm**

- [x] Sửa `TextCleaner.clean` để có tham số `lowercase: bool = True`.
- [x] Trong pipeline ingest, gọi `clean(text, lowercase=False)` để giữ nguyên
      chữ hoa/thường.
- [x] Chuẩn hóa Unicode NFC, khoảng trắng, ký tự điều khiển.
- [x] Tách `Điều`, `Khoản`, `Điểm` bằng regex; lưu `article_no`, `clause_no`,
      `point_no` vào metadata từng chunk.
- [x] Sinh `citation_label`/`citation` từ metadata, không từ LLM.
- [x] Chuẩn hóa ngày về `YYYY-MM-DD` trong DB/manifest; hiển thị `dd/mm/yyyy`.
- [x] Giữ `source_url` trong metadata nội bộ, không đưa vào citation.

**File dự kiến**

- `backend/app/rag/ingestion/cleaner.py` (sửa).
- `backend/app/rag/ingestion/pipeline.py` (sửa).
- `backend/app/rag/ingestion/citation.py` (mới).
- `backend/app/rag/ingestion/legal_structure.py` (mới).
- `backend/scripts/an_phu_ingest.py` (sửa).
- `backend/tests/unit/test_legal_structure.py` (mới).

**Điều kiện qua phase**

- [x] 100% văn bản An Phú có `citation_label` (51/51).
- [x] 94,1% văn bản nhận diện ít nhất một `Điều` (48/51; 3 văn bản không có
      cấu trúc Điều: `an_phu_2467`, `an_phu_2468`, `an_phu_2777`).
- [x] Chunk phụ lục/bảng không bị gắn `Điều` cuối; đã nhận diện 43 phụ lục.
- [x] `OutputValidator` kiểm tra citation và chặn ID/file nội bộ.
- [x] Không còn text lưu Chroma bị lowercase toàn bộ: 2.326 chunk An Phú giữ
      case; quét lại 2026-11-07 trên 4.405 chunk ≥100 ký tự chỉ còn 15 (0,3%)
      toàn chữ thường — là mẩu câu nguồn sẵn không có chữ hoa (vd `151-2025-ND-CP`),
      không phải lỗi transform.
- Không có citation chứa URL.

---

### Phase 5 — Ingest nền pháp lý từ HF dataset (1–2 ngày)

**Việc cần làm**

- [x] Tải `metadata`, `content`, `relationships` từ current configs.
- [x] Dùng `pyarrow.dataset` để đọc theo batch, không load toàn bộ vào RAM.
- [x] Lọc metadata:
  - TP.HCM: `co_quan_ban_hanh` hoặc `pham_vi` chứa `Hồ Chí Minh`.
  - Trung ương: lĩnh vực ưu tiên, loại văn bản phù hợp.
  - `tinh_trang_hieu_luc = Còn hiệu lực`.
  - Loại bỏ văn bản hết hiệu lực/hết hiệu lực một phần nếu không cần.
- [x] Join `metadata.id` với `content.id`.
- [x] Drop 732 dòng thiếu content; log danh sách ID.
- [x] Deduplicate theo `id` và `so_hieu`.
- [x] Chuẩn hóa metadata sang schema chung.
- [x] Ingest theo batch, checkpoint theo `doc_id`.
- [x] Ghi `hf_manifest.json` với số lượng trước/sau lọc.

**Lĩnh vực ưu tiên**

- Hộ tịch, cư trú, chứng minh nhân dân/căn cước.
- Đất đai, xây dựng, nhà ở.
- Khiếu nại, tố cáo, tiếp công dân.
- Ngân sách, đầu tư công cấp xã.
- Lao động, bảo trợ xã hội, y tế, giáo dục.
- Hôn nhân và gia đình.
- Doanh nghiệp, hộ kinh doanh.
- Thủ tục hành chính nói chung.

**Giới hạn**

- First pass đặt cap mềm **10.000 văn bản** để tránh ingest toàn bộ 171k.
- Nếu số lượng sau lọc < 10.000, ingest toàn bộ.
- Nếu > 10.000, ưu tiên TP.HCM trước, sau đó trung ương theo lĩnh vực/ngày ban hành.

**Điều kiện qua phase**

- Log rõ `metadata_total`, `after_filter`, `after_join`, `after_dedup`.
- 0 chunk có `doc_scope` rỗng.
- 0 chunk có `citation_label` rỗng.
- 10 văn bản mẫu được đối chiếu với `vbpl.vn`.

---

### Phase 6 — Ingest TTHC từ DVC (1 ngày)

**Việc cần làm**

- [x] Gọi list `level=COMMUNE`, `limit=200`, phân trang đến hết 1.506.
- [x] Thử lọc theo `wardCode=25975`; nếu 0 kết quả, ghi rõ fallback
      (test 10+ biến thể → 0 TTHC; fallback 1.506 TTHC COMMUNE toàn quốc +
      `applies_to_an_phu=true`; xác minh ghi trong `profile.yaml` khối `verification`).
- [x] Lưu raw JSON từng thủ tục.
- [x] Fetch detail theo UUID, rate limit 1 req/s (tuần tự).
- [x] Chuẩn hóa `required_documents`, `processing_time`, `fee`, `legal_basis`.
- [x] Ghi `procedures.jsonl`.
- [x] Đánh dấu `applies_to_an_phu` (hiện toàn bộ 1.506).

**Điều kiện qua phase**

- 1.506 list rows.
- Detail coverage ≥ 95%; các case lỗi có retry log.
- 0 `procedure_id` trùng.
- 10 thủ tục mẫu kiểm tra đúng tên, thời gian, lệ phí.

---

### Phase 7 — Ingest An Phú vào Chroma + BM25 (1 ngày)

**Việc cần làm**

- [x] Ingest 51/52 văn bản local có text (1 metadata-only `an_phu_2789`).
- [x] Ingest `profile.yaml`, `schedules.json`, `procedures.jsonl`.
- [x] Gắn metadata đầy đủ cho từng chunk.
- [x] Dùng stable chunk ID: `{document_id}_{chunk_index}`.
- [x] Rebuild BM25 một lần sau khi ingest xong.
- [x] Kiểm tra `Chroma count == BM25 corpus size` (8.860).
- [x] Chạy lại ingest `an_phu_2454` để xác nhận idempotent (count không tăng).

**Điều kiện qua phase**

- [x] Không tăng chunk count khi chạy lại.
- [x] Query local trả về chunk `doc_scope=local` trước (Phase 8).
- [x] Query profile/schedule/procedure trả đúng `doc_type`.
- [x] BM25 index load lại được sau khi restart.

---

### Phase 8 — Retrieval, citation và prompt (1–1,5 ngày)

**Việc cần làm**

- [x] Thêm `where`/filter vào `VectorStore.search`.
- [x] Thêm filter vào `Retriever.retrieve` và `HybridRetriever.retrieve`.
- [x] BM25 over-fetch rồi lọc metadata trước khi RRF.
- [x] Thêm `locality_code` vào pipeline/API; mặc định `25975` cho pilot.
- [x] Local-first, fallback global nếu thiếu kết quả.
- [x] Sửa prompt để yêu cầu citation từ `citation_label`.
- [x] Sửa `OutputValidator` để kiểm tra:
  - Có ít nhất một citation.
  - Citation khớp metadata.
  - Không có URL.
  - Không có số hiệu không tồn tại trong context.
- [x] Trả `citation`, `doc_number`, `issued_date`, `issuer`, `doc_scope` trong
      `source_chunks` (P8: `ChunkReference` + `sources_payload` + API test).

**Điều kiện qua phase**

- 20 câu hỏi vàng trả citation đúng.
- Không có câu trả lời chứa URL.
- Câu hỏi local không bị trả bằng văn bản trung ương nếu có văn bản local.
- Câu hỏi global vẫn fallback được.

---

### Phase 9 — API, schema và UI (1 ngày)

> **Hoàn thành 2026-11-07 (file-backed — quyết định demo)**: 3 endpoint đọc
> trực tiếp `data/localities/an_phu/` (profile.yaml, schedules.json,
> manifest.json, procedures.jsonl) + cache process, field-whitelist nên
> `source_url/pdf_url/portal` không bao giờ ra API. **Không** tạo bảng DB/
> `init_db` và **không** thêm bảng `legal_articles` (điều khoản Điều/Khoản đã
> nằm trong metadata chunk qua `legal_structure.annotate_chunks`; hoãn sang
> phase DB nếu cần persist). Tests: `backend/tests/api/test_locality_api.py`.

**Việc cần làm**

- [x] Thêm bảng DB và cập nhật `scripts/init_db.py`.
      (hoãn — demo đọc file trực tiếp, xem note trên)
- [x] Thêm schema Pydantic cho locality/profile/legal/procedure.
      (`app/schemas/locality.py` — 10 model, không field URL)
- [x] Thêm endpoint tối thiểu:
  - `GET /api/v1/localities/an-phu/profile`
  - `GET /api/v1/procedures?locality_code=25975&q=...`
  - `GET /api/v1/legal-documents?locality_code=25975`
- [x] Cập nhật `POST /api/v1/chat/query` nhận `locality_code`
      (đã làm trong Phase 8 — mặc định `25975`, có API test).
- [x] Cập nhật frontend source card hiển thị citation, không hiển thị URL.
      (`script.js` `buildSourceCard`: 1 nguồn `source_chunks[0]` + badge
      doc_type/scope; `style.css` `.source-card`; `strip_urls()` ở
      `RAGResponse.to_dict` + `sources_payload`)
- [x] Giữ nguyên auth/conversation/admin hiện có.
      (488 passed / 0 failed — chỉ mở rộng test thêm `doc_type`)

**Điều kiện qua phase**

- [x] API docs `/docs` hiển thị endpoint mới (verify `openapi.json` 2026-11-07).
- [x] Chat response có citation đúng format
      (eval 2026-11-07: citation_recall 1.000).
- [x] UI không render URL trong citation
      (card chỉ render badge/citation/độ ngày-cơ quan; `text` đã strip URL).
- [x] Không vỡ test auth/conversation/admin (488 passed / 3 skipped / 0 fail).

---

### Phase 10 — Test, evaluation và bàn giao (1 ngày)

**Unit test**

- [x] `manifest` validator: đủ trường, không trùng, ngày hợp lệ.
- [x] `citation_label` builder: có/không số hiệu, có/không ngày.
- [x] `TextCleaner` giữ chữ hoa khi `lowercase=False`.
- [x] `VectorStore` merge metadata đúng.
- [x] Filter local/global trả đúng `doc_scope`.
- [x] `OutputValidator` bắt citation thiếu/URL/sai (thêm chặn URL 2026-11-07).

**Integration test**

- [x] Ingest 3 văn bản An Phú giả lập vào Chroma tạm.
- [x] Query local trả đúng chunk.
- [x] Query fallback global trả đúng chunk.
- [x] Rebuild BM25 khớp Chroma.
- [x] Test thật với An Phú đặt sau marker `@pytest.mark.real_ingestion`.

**API test**

- [x] Chat với `locality_code=25975`.
- [x] Chat không truyền `locality_code` vẫn mặc định An Phú.
- [x] Response `source_chunks` có citation.
- [x] Không có URL trong citation.

**Evaluation**

- [x] 30 câu hỏi vàng:
  - 10 câu về văn bản local.
  - 10 câu về TTHC.
  - 5 câu về lịch làm việc.
  - 5 câu về profile/liên hệ.
- [x] Đo `retrieval@5` (document-level): HitRate@5 1.00, MRR 0.881.
- [x] Chạy answer eval 30 câu: citation recall 1.00, term recall 0.944.
- [x] Đưa answer-level citation accuracy lên 100% (2026-11-07: 30/30 câu qua
      `OutputValidator`, citation recall 1.000, term recall 0.963 — số liệu
      `citation_precision` 0.470 là precision của top-5 chunk truy xuất, bị
      chặn bởi `k=5`, không phải độ chính xác trích dẫn; giải thích ở
      `backend/docs/AN_PHU_EVAL.md` §6).
- [x] Mục tiêu: `retrieval@5 ≥ 80%` (đạt 1.00), `citation_accuracy = 100%`,
      `0 URL`, `0 citation bịa`.

**Điều kiện qua phase**

- `pytest tests/unit tests/api -q` pass.
- Integration An Phú pass khi bật marker.
- Báo cáo evaluation lưu trong `backend/docs/AN_PHU_EVAL.md`.

---

## 7. Thay đổi code dự kiến

| File | Thay đổi | Lý do |
|---|---|---|
| `backend/scripts/an_phu_fetch.py` | Mới: fetch API, lịch, profile, PDF, manifest | Tự động hóa snapshot An Phú |
| `backend/scripts/an_phu_prepare.py` | Mới: extract/OCR, QA, cập nhật manifest | OCR 46 PDF scan có checkpoint |
| `backend/scripts/ingest_hf_legal.py` | Mới: lọc/join/ingest HF | Không load 4,37 GB vào RAM |
| `backend/scripts/ingest_an_phu.py` | Mới: ingest local + profile + lịch + TTHC | Gắn metadata/citation đúng |
| `backend/app/rag/ingestion/manifest.py` | Mới: schema + validator | Chặn dữ liệu thiếu/trùng |
| `backend/app/rag/ingestion/citation.py` | Mới: sinh citation từ metadata | Không để LLM bịa nguồn |
| `backend/app/rag/ingestion/legal_structure.py` | Mới: tách Điều/Khoản/Điểm | Citation chi tiết |
| `backend/app/rag/ingestion/cleaner.py` | Thêm `lowercase` flag | Giữ chữ hoa cho citation |
| `backend/app/rag/ingestion/pipeline.py` | Nhận metadata, giữ case | Gắn provenance |
| `backend/app/models/data_models.py` | Thêm metadata cho `Document`/`Chunk` | Mang metadata đến Chroma |
| `backend/app/database/vector_store.py` | Merge metadata, thêm `where` | Filter theo địa phương |
| `backend/app/rag/retrieval/retriever.py` | Thêm `where` | Local-first |
| `backend/app/rag/retrieval/hybrid_retriever.py` | Filter vector + BM25 | Tránh trộn nguồn |
| `backend/app/rag/pipeline/hybrid_rag_pipeline.py` | Truyền filter, citation | Pipeline end-to-end |
| `backend/app/rag/generation/llm_service.py` | Prompt citation | Buộc trích dẫn đúng |
| `backend/app/rag/generation/output_validator.py` | Check citation/URL | Chặn hallucination |
| `backend/app/api/chat.py` | Nhận `locality_code`, trả citation | API cho An Phú |
| `backend/app/models/db_models.py` | Thêm bảng locality/legal/procedure | Metadata bền vững |
| `backend/scripts/init_db.py` | Tạo bảng mới | DB demo đầy đủ |
| `backend/requirements.txt` | Thêm `huggingface_hub`, `pyarrow` | Đọc HF parquet |
| `backend/tests/...` | Test manifest/citation/filter/API | Chống regression |

---

## 8. API và UI

### 8.1. Chat request

```json
{
  "query": "Thủ tục đăng ký khai sinh cần giấy tờ gì?",
  "k": 5,
  "locality_code": "25975"
}
```

`locality_code` mặc định `25975` trong pilot; nếu không truyền vẫn ưu tiên An Phú.

### 8.2. Source chunk response

```json
{
  "document_id": "an_phu_2788",
  "text": "...",
  "similarity_score": 0.91,
  "chunk_index": 3,
  "citation": "Nghị quyết số 25/NQ-HĐND ngày 29/7/2026 của HĐND phường An Phú, Điều 3, khoản 2",
  "doc_number": "25/NQ-HĐND",
  "issued_date": "2026-07-29",
  "issuer": "HĐND phường An Phú",
  "doc_scope": "local"
}
```

- Không trả URL trong `citation`.
- `source_url` chỉ dùng nội bộ/admin, không render ở source card.

### 8.3. UI

- Source card hiển thị:
  - Tiêu đề hoặc citation.
  - Số hiệu + ngày ban hành.
  - Cơ quan ban hành.
  - Điều/Khoản nếu có.
- Không hiển thị link ra ngoài.
- Có badge `Văn bản phường`, `TTHC`, `Lịch làm việc`, `Văn bản TP.HCM`.

---

## 9. Kiểm thử và đánh giá

### 9.1. Câu hỏi vàng mẫu

1. Thủ tục đăng ký khai sinh cần giấy tờ gì?
2. Cấp bản sao trích lục hộ tịch mất bao lâu?
3. Lịch tiếp công dân của phường An Phú tháng này?
4. Quy chế tiếp công dân của phường quy định gì?
5. Thông báo sắp xếp khu phố số mấy?
6. Ngân sách phường năm 2026 được quy định ở văn bản nào?
7. Địa chỉ UBND phường An Phú?
8. Giờ làm việc của phường An Phú?
9. Thủ tục nào thuộc thẩm quyền cấp phường?
10. Căn cứ pháp lý của thủ tục khai sinh?
11. Văn bản trung ương nào quy định về hộ tịch?
12. Hồ sơ cư trú gồm những gì?
13. Thủ tục xây dựng nhà ở cấp phường?
14. Khiếu nại về đất đai gửi ở đâu?
15. Lịch làm việc của lãnh đạo phường?
16. Văn bản nào quy định về tiếp công dân?
17. Thủ tục hộ kinh doanh cấp phường?
18. Lệ phí đăng ký khai sinh?
19. Thời gian giải quyết thủ tục khai sinh?
20. Văn bản phường nào đang còn hiệu lực?

### 9.2. Chỉ số

| Chỉ số | Mục tiêu | Cách đo |
|---|---:|---|
| `retrieval@5` | ≥ 80% | Câu trả lời có chunk đúng trong top 5 |
| `citation_accuracy` | 100% | Citation khớp metadata |
| `url_in_citation` | 0 | Regex URL trong citation |
| `hallucinated_doc_number` | 0 | So khớp với manifest/DB |
| `local_first` | ≥ 90% | Câu hỏi local trả chunk local trước |
| `ocr_doc_success` | 46/46 | Manifest `ocr_status=ocr` |
| `procedure_detail_coverage` | ≥ 95% | Có raw detail |
| `chunk_duplicate` | 0 | Chạy ingest 2 lần |

### 9.3. Lệnh kiểm tra

```bash
cd local-government-ai-assistant/backend
source .venv/bin/activate

# Unit + API
python -m pytest tests/unit tests/api -q

# Integration An Phú (bật marker)
python -m pytest tests/integration/test_an_phu_ingestion.py -q -m real_ingestion

# Kiểm tra manifest
python scripts/an_phu_prepare.py --data-dir data/localities/an_phu --validate-only

# Kiểm tra Chroma/BM25
python -c "from app.core.dependencies import get_vector_store; print(get_vector_store().get_collection_stats())"
```

---

## 10. Rủi ro và cách giảm thiểu

| Rủi ro | Mức | Cách giảm |
|---|---|---|
| OCR sai tiếng Việt, mất dấu | Cao | Dùng `tesseract-ocr-vie`, 400 DPI, spot-check 10 văn bản, đối chiếu ảnh |
| PDF scan có bảng biểu bị mất cấu trúc | Cao | OCR + pdfplumber; lưu bảng thành text có thứ tự; QA thủ công |
| `id=2789` không có PDF | Trung bình | Đánh dấu `missing_pdf`; chỉ dùng trích yếu; không claim toàn văn |
| PDF `2459`, `2835` lỗi tải | Trung bình | Retry/backoff; lưu log; chạy lại idempotent |
| Mã `25975` sai | Cao | Xác minh DVC/LGSP trước khi ghi DB; không hard-code nếu chưa chắc |
| DVC rate limit | Trung bình | Concurrency 2, 1 req/s, cache raw JSON, resume |
| HF dataset quá lớn | Cao | `pyarrow` batch, filter trước, cap 10k, checkpoint |
| 732 dòng thiếu content | Thấp | Drop + log; không ingest metadata rỗng |
| LLM bịa số hiệu | Cao | Citation từ metadata; validator check; prompt nghiêm |
| Lowercase làm mất số hiệu | Cao | `lowercase=False` khi lưu; chỉ lowercase token BM25 |
| Chunk trùng khi chạy lại | Trung bình | Stable `document_id` + `chunk_index`; upsert |
| BM25 rebuild lâu | Trung bình | Chỉ rebuild một lần sau batch; không rebuild mỗi file |
| Metadata Chroma có `None` | Trung bình | Convert `None` → `""`; validate trước upsert |
| Test integration cũ fail | Trung bình | Đánh marker `real_ingestion`; skip mặc định; sửa dần |

---

## 11. Thứ tự thực hiện và ước lượng

| Ngày | Phase | Kết quả |
|---:|---|---|
| 1 | P0 + P1 | Xác minh địa phương, manifest 52 văn bản, 18 lịch |
| 2 | P2 | 53 PDF + checksum |
| 3 | P3 | OCR 46 PDF + text 53 PDF (51 văn bản) |
| 4 | P4 | Chuẩn hóa, Điều/Khoản, citation |
| 5–6 | P5 | Lọc + ingest HF foundation |
| 7 | P6 | 1.506 TTHC + detail |
| 8 | P7 | Ingest An Phú, Chroma + BM25 |
| 9 | P8 | Retrieval filter + citation + prompt |
| 10 | P9 + P10 | API/UI, test, evaluation, bàn giao |

Tổng: **10 ngày làm việc** cho 2 sinh viên, chưa tính thời gian chờ model embedding
và thời gian debug OCR.

---

## 12. Checklist bàn giao

- [x] `docs/PLAN_AN_PHU.md` được cập nhật trạng thái từng phase
      (2026-11-07; đủ 10 phase — Phase 9 xong theo hướng file-backed).
- [x] `backend/data/localities/an_phu/manifest.json` đủ 52 entry.
- [x] 18 lịch trong `backend/data/localities/an_phu/schedules.json`; thông tin
      liên hệ + xác minh ward trong `profile.yaml`.
- [x] `backend/data/localities/an_phu/procedures.jsonl` có TTHC (1.506 dòng).
- [x] `backend/data/legal_hf/hf_manifest.json` có số liệu lọc.
- [x] Chroma có chunk local + global + procedure + profile + schedule
      (23.949 chunk: central 13.660 / local 8.103 / hcmc 2.186).
- [x] BM25 index rebuild thành công (corpus khớp Chroma).
- [x] Chat trả citation đúng, không URL (eval 2026-11-07: 30/30, 0 URL).
- [x] 30 câu hỏi vàng có báo cáo (`backend/docs/AN_PHU_EVAL.md`).
- [x] Test unit/API pass; integration An Phú có marker
      (477 passed / 3 skipped / 1 deselected / 0 failed).
- [x] `CHANGELOG.md` được append nếu task sửa ≥ 3 file code.
- [x] Không commit `.env`, PDF dung lượng lớn hoặc `chroma_db/` vào git
      (đã verify `git check-ignore`; backup index mới cũng thêm vào `.gitignore`).

---

## Phụ lục A — Lệnh chạy đề xuất

```bash
cd local-government-ai-assistant/backend
source .venv/bin/activate

# 1. Snapshot + tải PDF
python scripts/an_phu_fetch.py \
  --data-dir data/localities/an_phu \
  --download

# 2. Extract + OCR + QA
python scripts/an_phu_prepare.py \
  --data-dir data/localities/an_phu \
  --ocr

# 3. Ingest nền pháp lý HF (lọc trước)
python scripts/ingest_hf_legal.py \
  --out data/legal_hf \
  --max-docs 10000

# 4. Ingest An Phú + profile + lịch + TTHC
python scripts/ingest_an_phu.py \
  --data-dir data/localities/an_phu

# 5. Kiểm tra
python -m pytest tests/unit tests/api -q
python -m pytest tests/integration/test_an_phu_ingestion.py -q -m real_ingestion
```

## Phụ lục B — Giả định cần xác minh

- `25975` là mã hành chính chính thức của Phường An Phú.
- DVC có hỗ trợ lọc TTHC theo `wardCode=25975`; nếu không, dùng danh sách
  `COMMUNE` toàn quốc và gắn ngữ cảnh An Phú.
- HF dataset giữ nguyên schema tại snapshot `2026-07-23`.
- Các trường `co_quan_ban_hanh`, `pham_vi`, `tinh_trang_hieu_luc` đủ để lọc
  TP.HCM/trung ương; nếu thiếu, dùng `relationships` hoặc regex fallback.
- `id=2789` không thể tìm được PDF từ nguồn khác; nếu tìm được, cập nhật manifest
  và OCR bổ sung.
