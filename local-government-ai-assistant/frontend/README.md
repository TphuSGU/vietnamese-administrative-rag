# RAG Chat UI

Giao diện chat tĩnh (HTML/CSS/JS) cho trợ lý tra cứu văn bản hành chính. Không cần build tool.

## Chạy

```bash
# Terminal 1: backend
cd backend
source .venv/bin/activate
python -m app.main

# Terminal 2: frontend
cd frontend
python -m http.server 3000
```

Mở http://localhost:3000.

Backend mặc định `http://localhost:8000`; CORS cho phép `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173` (xem `CORS_ORIGINS` trong `backend/.env`).

## Tính năng

- Chat ẩn danh với RAG API.
- Đăng ký/đăng nhập, lưu token trong `localStorage`.
- Lưu lịch sử hội thoại khi đã đăng nhập; sidebar chọn lại hội thoại cũ.
- Nút "Cuộc hội thoại mới".
- Hiển thị câu trả lời, nguồn tham khảo (document + chunk), thời gian xử lý và model.
- Validate câu hỏi 10–500 ký tự, chặn gửi trùng khi đang chờ.
- Responsive; sidebar mở bằng nút ☰ trên mobile.

## API dùng bởi frontend

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET/POST /api/v1/conversations`
- `GET/DELETE /api/v1/conversations/{id}`
- `POST /api/v1/chat/query` (gửi `conversation_id` khi đã chọn hội thoại)

Đổi backend URL trong `script.js`:

```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1';
```

## Câu hỏi mẫu

- "Nghị định 150/2025/NĐ-CP quy định về tổ chức cơ quan chuyên môn thuộc UBND cấp nào?"
- "Cơ quan chuyên môn thuộc UBND cấp tỉnh và cấp xã được gọi là gì?"
- "Luật 65/2025/QH15 quy định chính quyền địa phương có mấy cấp?"
- "Nghị định 151/2025/NĐ-CP quy định chức năng gì?"

## Lưu ý

- Phải chạy qua HTTP server, không mở trực tiếp `file://`, vì CORS origin `null` sẽ bị chặn.
- Token hết hạn (mặc định 24h) sẽ tự đăng xuất và xóa phiên.
- Nếu backend đổi port, sửa `API_BASE_URL` hoặc thêm origin mới vào `CORS_ORIGINS`.
