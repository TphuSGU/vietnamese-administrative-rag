# Đưa repo lên Colab để ingest HF Phase 5

Mục tiêu: chạy `scripts/hf_legal_ingest.py` trên GPU T4 cho phần còn lại của
10.000 văn bản HF, sau đó tải `chroma_db` + `bm25s_index` về máy.

> Trạng thái 2026-11-04: **tạm hoãn**, sẽ chạy sau và phối hợp đánh giá truy xuất
> với **AITeamVN**. Tài liệu này giữ lại để dùng khi quay lại Phase 5.

## 1. Chuẩn bị file ở máy local

Đã có sẵn sau bước filter + pilot:

```text
backend/data/legal_hf/hf_manifest.json      8.8 MB
backend/data/legal_hf/hf_documents.jsonl    175 MB
```

Nếu muốn **resume từ 500 văn bản đã ingest**, cần thêm:

```text
backend/chroma_db/        489 MB
backend/bm25s_index/       94 MB
```

Nén code (không đưa `.venv`, raw HF, chroma cũ vào zip code):

```bash
cd /home/tphu/Desktop/Tphu/SchoolCode/Specially\ Project/Administrative_AI

zip -r hf_colab_code.zip \
  local-government-ai-assistant/backend/app \
  local-government-ai-assistant/backend/scripts \
  local-government-ai-assistant/backend/evaluation \
  local-government-ai-assistant/backend/tests \
  local-government-ai-assistant/backend/requirements.txt \
  local-government-ai-assistant/backend/.env.example \
  local-government-ai-assistant/docs \
  -x '*/.venv/*' '*__pycache__*' '*.pyc'
```

Nén dữ liệu để upload Drive:

```bash
cd local-government-ai-assistant
zip -r hf_data_500.zip \
  backend/data/legal_hf/hf_manifest.json \
  backend/data/legal_hf/hf_documents.jsonl \
  backend/chroma_db backend/bm25s_index
```

Kiểm tra kích thước trước khi upload. Nếu mạng chậm, có thể **bỏ
`chroma_db` + `bm25s_index`** và chạy lại từ đầu trên T4; 10k văn bản trên T4
vẫn nhanh hơn upload 583 MB.

## 2. Upload lên Google Drive

Upload lên Drive:

```text
MyDrive/hf_colab/hf_colab_code.zip
MyDrive/hf_colab/hf_data_500.zip
```

Không upload trực tiếp vào `/content` bằng trình duyệt nếu file lớn; dùng Drive.

## 3. Mở Colab

Chọn runtime:

```text
Runtime → Change runtime type → T4 GPU
```

Kiểm tra GPU:

```python
!nvidia-smi
import torch
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
```

Kết quả phải có `True` và `Tesla T4`.

## 4. Mount Drive và copy vào ổ local

Quan trọng: **copy từ Drive sang `/content`** rồi mới chạy. Đọc trực tiếp
Chroma/JSONL từ Drive rất chậm và dễ lỗi session.

```python
from google.colab import drive
drive.mount('/content/drive')

!mkdir -p /content/work
!cp "/content/drive/MyDrive/hf_colab/hf_colab_code.zip" /content/work/
!cp "/content/drive/MyDrive/hf_colab/hf_data_500.zip" /content/work/
!cd /content/work && unzip -q hf_colab_code.zip
!cd /content/work && unzip -q hf_data_500.zip
```

Sau khi giải nén, kiểm tra:

```python
!ls -lh /content/work/local-government-ai-assistant/backend/data/legal_hf
!du -sh /content/work/local-government-ai-assistant/backend/chroma_db
```

## 5. Cài dependency

```python
%cd /content/work/local-government-ai-assistant/backend
!pip install -q -r requirements.txt
```

Kiểm tra lại GPU sau khi cài, vì một số gói có thể kéo torch CPU:

```python
import torch
print(torch.cuda.is_available(), torch.__version__)
```

Nếu `False`:

```python
!pip install -q --force-reinstall torch --index-url https://download.pytorch.org/whl/cu121
```

## 6. Set biến môi trường

Không cần gọi Gemini để ingest, nhưng app yêu cầu key không rỗng:

```python
import os
os.environ["GEMINI_API_KEY"] = "dummy-for-ingest"
os.environ["EMBEDDING_BATCH_SIZE"] = "64"   # T4: 64; OOM thì giảm 32
os.environ["HF_HOME"] = "/content/hf_cache"
os.environ["TRANSFORMERS_CACHE"] = "/content/hf_cache"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
```

T4 16 GB nên bắt đầu `64`, không nên đặt `128` ngay.

## 7. Chạy thử 20 văn bản

Nếu đã upload Chroma pilot, script tự skip 500 văn bản đã có. Chạy thử không
embed:

```bash
python scripts/hf_legal_ingest.py --offset 500 --limit 20 --dry-run
```

Sau đó chạy thật 20 văn bản:

```bash
python -u scripts/hf_legal_ingest.py --offset 500 --limit 20 --no-rebuild-bm25
```

Xem tốc độ `chunks/s`. Trên T4 kỳ vọng khoảng **80–200 chunk/s**; nếu thấp hơn
30 chunk/s thì kiểm tra GPU/batch size.

## 8. Chạy phần còn lại

Nếu dùng Chroma pilot:

```bash
python -u scripts/hf_legal_ingest.py --offset 500 --no-rebuild-bm25
```

Nếu **không** upload Chroma cũ, chạy từ đầu:

```bash
python -u scripts/hf_legal_ingest.py --no-rebuild-bm25
```

Nên chạy trong cell có `nohup` để không mất log nếu notebook disconnect:

```bash
nohup python -u scripts/hf_legal_ingest.py --offset 500 --no-rebuild-bm25 \
  > /content/work/hf_ingest.log 2>&1 &
tail -f /content/work/hf_ingest.log
```

Script resume theo `document_id`: nếu session chết, chạy lại cùng lệnh sẽ skip
văn bản đã ghi.

## 9. Rebuild BM25 sau khi xong

```bash
python - <<'PY'
from app.core.config import settings
from app.core.dependencies import get_vector_store
from app.rag.retrieval.index_manager import rebuild_bm25_index

vs = get_vector_store()
index = rebuild_bm25_index(
    vs, settings.bm25s_persist_dir, settings.bm25s_k1, settings.bm25s_b
)
print(vs.get_collection_stats())
print(index.get_stats() if index else None)
PY
```

## 10. Kiểm tra và tải kết quả về

```bash
python - <<'PY'
from app.core.dependencies import get_vector_store
print(get_vector_store().get_collection_stats())
PY
```

Nén kết quả:

```bash
cd /content/work/local-government-ai-assistant/backend
zip -r /content/work/hf_ingest_result.zip chroma_db bm25s_index \
  data/legal_hf/hf_ingest_report.json
```

Copy về Drive:

```python
!cp /content/work/hf_ingest_result.zip "/content/drive/MyDrive/hf_colab/"
```

Tải file zip về máy, giải nén đè vào:

```text
backend/chroma_db/
backend/bm25s_index/
backend/data/legal_hf/hf_ingest_report.json
```

## 11. Lưu ý

- Không ghi Chroma trực tiếp vào Drive.
- Không chạy `--reset`.
- Nếu Colab hết RAM/VRAM: giảm `EMBEDDING_BATCH_SIZE` xuống `32`.
- Nếu session chết giữa chừng: chạy lại cùng lệnh; script skip `document_id` đã
  có trong Chroma.
- Sau khi full 10k, chạy lại 30 câu An Phú và 50 câu luật để kiểm tra phân bố
  retrieval.
