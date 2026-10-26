# OCR cho PDF scan

`DocumentLoader` dùng `pytesseract` + Tesseract để OCR trang PDF không có text layer. Nếu máy chưa có `tesseract` và `vie.traineddata`, ingest PDF scan sẽ báo `No text content extracted`.

## Cài không cần sudo (Ubuntu/Debian)

```bash
cd local-government-ai-assistant/backend
bash scripts/setup_tesseract_local.sh
export PATH="$PWD/.tesseract/bin:$PATH"
```

Script tải 4 gói `.deb` (`tesseract-ocr`, `tesseract-ocr-vie`, `libtesseract5`, `liblept5`), giải nén vào `backend/.tesseract/`, và tạo wrapper `tesseract` tự set `LD_LIBRARY_PATH` + `TESSDATA_PREFIX`. Thư mục `.tesseract/` đã được `.gitignore`.

Kiểm tra:

```bash
tesseract --version
tesseract --list-langs   # phải có vie
```

## Cài bằng apt (nếu có sudo)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-vie
```

## Cấu hình

Mặc định trong `app/core/config.py`:

- `OCR_ENABLED=true`
- `OCR_LANG=vie`
- `OCR_DPI=150`
- `OCR_MIN_CHARS_PER_PAGE=100`
- `OCR_MAX_PAGES=0` (0 = OCR tất cả trang thiếu text)

Có thể override bằng biến môi trường trong `backend/.env`.

## Kiểm tra nhanh

```bash
export PATH="$PWD/.tesseract/bin:$PATH"
.venv/bin/python - <<'PY'
from app.rag.ingestion.loader import DocumentLoader
d = DocumentLoader(ocr_enabled=True, ocr_lang="vie", ocr_max_pages=0).load_document(
    file_path="../../150nd.signed.pdf"
)
print(len(d.text))
print(d.text[:500])
PY
```

Kết quả đã kiểm tra trên `150nd.signed.pdf` (20 trang scan): ~39.800 ký tự, có `Điều 1`, `Điều 2`, `Điều 3`; thời gian OCR ~21 giây ở DPI 150.

## Lưu ý

- OCR chạy tuần tự từng trang; PDF scan dài nên tăng `OCR_DPI` sẽ chậm và tốn RAM.
- `OCR_MAX_PAGES` giới hạn số trang OCR mỗi tài liệu, hữu ích khi test.
- Corpus production hiện dùng PDF có text layer (đã merge), nên OCR chỉ dùng cho upload PDF scan.
