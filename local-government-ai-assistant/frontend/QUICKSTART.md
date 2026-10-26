# Quick Start

## 1. Backend

```bash
cd backend
source .venv/bin/activate
python -m app.main
```

Backend: http://localhost:8000, docs: http://localhost:8000/docs.

## 2. Frontend

```bash
cd frontend
python -m http.server 3000
```

Mở http://localhost:3000.

## 3. Thử chat

Không cần đăng nhập:

- "Nghị định 150/2025/NĐ-CP quy định về tổ chức cơ quan chuyên môn thuộc UBND cấp nào?"
- "Cơ quan chuyên môn thuộc UBND cấp tỉnh và cấp xã được gọi là gì?"
- "Luật 65/2025/QH15 quy định chính quyền địa phương có mấy cấp?"

Đăng nhập/đăng ký để lưu lịch sử. Sau khi đăng nhập, sidebar hiển thị các cuộc hội thoại cũ.

## Lỗi thường gặp

- **CORS**: backend phải chạy và `CORS_ORIGINS` chứa origin frontend (`http://localhost:3000`).
- **Connection refused**: kiểm tra backend port 8000.
- **401 khi chat**: token hết hạn, đăng nhập lại.
- **Không thấy lịch sử**: phải đăng nhập; chat ẩn danh không được lưu.
