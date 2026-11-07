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
- Đổi tên/xóa hội thoại ngay trên sidebar.
- Hiển thị câu trả lời kèm citation pháp lý, thời gian xử lý và model.
- Validate câu hỏi tối thiểu 10 ký tự, không giới hạn độ dài tối đa; chặn gửi trùng khi đang chờ.
- Gửi **ý kiến người dân** công khai: góp ý, phản ánh, kiến nghị, hỏi đáp.
- Responsive; sidebar mở bằng nút ☰ trên mobile.
- Trang cán bộ `admin.html`: thống kê, tải tài liệu, theo dõi job, danh sách/xóa tài liệu, quản lý người dùng và **tiếp nhận/xử lý ý kiến người dân**.

## API dùng bởi frontend

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET/POST /api/v1/conversations`
- `GET/PATCH/DELETE /api/v1/conversations/{id}`
- `POST /api/v1/chat/query` (gửi `conversation_id` khi đã chọn hội thoại)
- `POST /api/v1/feedback`
- `GET /api/v1/feedback?status=...&page=...&page_size=...&search=...` (cán bộ)
- `PATCH /api/v1/feedback/{id}` (cán bộ)
- `GET /api/v1/admin/stats`
- `GET /api/v1/documents`, `POST /api/v1/documents`, `DELETE /api/v1/documents/{id}`
- `GET /api/v1/documents/jobs`, `GET /api/v1/documents/{job_id}`
- `GET /api/v1/users?role=all&page=1&page_size=10&search=...`, `PATCH /api/v1/users/{id}/role`

## Cấu hình API URL

Không sửa trực tiếp `script.js`. Dùng `config.js` hoặc query param:

```javascript
window.APP_CONFIG = { API_BASE_URL: 'https://api.example.com/api/v1' };
```

Hoặc mở `index.html?api=https://api.example.com/api/v1`. Mặc định frontend tự trỏ về
`http://<host>:8000/api/v1` cho môi trường local.

## Câu hỏi mẫu

- "Nghị định 150/2025/NĐ-CP quy định về tổ chức cơ quan chuyên môn thuộc UBND cấp nào?"
- "Cơ quan chuyên môn thuộc UBND cấp tỉnh và cấp xã được gọi là gì?"
- "Luật 65/2025/QH15 quy định chính quyền địa phương có mấy cấp?"
- "Nghị định 151/2025/NĐ-CP quy định chức năng gì?"

## Lưu ý

- Phải chạy qua HTTP server, không mở trực tiếp `file://`, vì CORS origin `null` sẽ bị chặn.
- Token hết hạn (mặc định 24h) sẽ tự đăng xuất và xóa phiên.
- Nếu backend đổi port, sửa `API_BASE_URL` hoặc thêm origin mới vào `CORS_ORIGINS`.
