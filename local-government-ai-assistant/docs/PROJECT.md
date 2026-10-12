# Dự án: Trợ lý ảo hỗ trợ tra cứu thông tin hành chính dựa trên RAG

## 1. Thông tin tổng quan

**Tên đề tài:** Xây dựng trợ lý ảo hỗ trợ tra cứu thông tin hành chính
dựa trên mô hình RAG cho chính quyền địa phương cấp cơ sở

**Tên tiếng Anh:** Development of a RAG-Based Virtual Assistant System
for Administrative Information Retrieval in Local Government

**Thời gian thực hiện:** 12 tuần

**Số lượng thành viên:** 2 sinh viên

**Công nghệ chính:** - Frontend: React - Backend: Python + FastAPI - Cơ
sở dữ liệu: PostgreSQL - Vector Database: có thể sử dụng ChromaDB,
Qdrant hoặc PostgreSQL + pgvector - AI/RAG: Python - LLM: mô hình API
hoặc mô hình triển khai phù hợp - Authentication: JWT -
Containerization: Docker / Docker Compose

------------------------------------------------------------------------

## 2. Mục tiêu dự án

Dự án xây dựng một hệ thống trợ lý ảo cho phép người dùng đặt câu hỏi
bằng ngôn ngữ tự nhiên về các thông tin hành chính ở cấp cơ sở.

Hệ thống sử dụng kiến trúc **Retrieval-Augmented Generation (RAG)** để
tìm kiếm các nội dung liên quan từ tập tài liệu hành chính trước khi đưa
thông tin này vào ngữ cảnh cho mô hình ngôn ngữ lớn (LLM).

Mục tiêu chính:

1.  Cho phép người dân đặt câu hỏi bằng ngôn ngữ tự nhiên.
2.  Tìm kiếm các văn bản/tài liệu hành chính có liên quan.
3.  Sinh câu trả lời dựa trên nội dung được truy xuất.
4.  Hiển thị nguồn tài liệu để người dùng kiểm chứng.
5.  Cho phép cán bộ/quản trị viên quản lý tài liệu phục vụ hệ thống RAG.
6.  Quản lý người dùng, phiên hội thoại và lịch sử trao đổi.
7.  Đánh giá chất lượng truy xuất và chất lượng câu trả lời.

> **Phạm vi quan trọng:** hệ thống tập trung vào **tra cứu và giải thích
> thông tin hành chính**, không thực hiện thay người dân các thủ tục
> hành chính hoặc đưa ra quyết định hành chính.

------------------------------------------------------------------------

## 3. Bài toán cần giải quyết

Thông tin hành chính thường được trình bày trong nhiều văn bản, tài liệu
và biểu mẫu. Người dùng có thể gặp khó khăn khi:

-   Không biết chính xác tên văn bản cần tìm.
-   Không biết từ khóa phù hợp.
-   Phải đọc nhiều tài liệu để tìm một thông tin cụ thể.
-   Đặt câu hỏi bằng ngôn ngữ tự nhiên nhưng hệ thống tìm kiếm truyền
    thống không hiểu đầy đủ ý định.
-   Khó xác định câu trả lời được lấy từ tài liệu nào.

Hệ thống đề xuất giải quyết vấn đề trên bằng cách kết hợp:

``` text
Người dùng
    ↓
Câu hỏi tự nhiên
    ↓
Semantic Search
    ↓
Tài liệu hành chính liên quan
    ↓
RAG
    ↓
LLM
    ↓
Câu trả lời + nguồn tham khảo
```

------------------------------------------------------------------------

## 4. Phạm vi chức năng

### 4.1. Người dùng

Người dùng có thể:

-   Đăng ký / đăng nhập.
-   Đặt câu hỏi cho trợ lý ảo.
-   Xem câu trả lời.
-   Xem nguồn tài liệu được sử dụng.
-   Xem lịch sử hội thoại.
-   Tạo cuộc hội thoại mới.
-   Xem thông tin cá nhân.

### 4.2. Quản trị viên

Quản trị viên có thể:

-   Quản lý người dùng.
-   Phân quyền người dùng.
-   Upload tài liệu.
-   Xem danh sách tài liệu.
-   Xóa tài liệu.
-   Theo dõi trạng thái xử lý tài liệu.
-   Kiểm tra dữ liệu đã được đưa vào Vector Database.

### 4.3. RAG

Hệ thống RAG thực hiện:

-   Đọc PDF/DOCX/TXT.
-   Trích xuất nội dung.
-   Làm sạch văn bản.
-   Chia văn bản thành các đoạn nhỏ (chunk).
-   Tạo embedding.
-   Lưu vector và metadata.
-   Tìm kiếm semantic.
-   Lấy Top-K đoạn văn bản liên quan.
-   Xây dựng prompt.
-   Gửi context và câu hỏi đến LLM.
-   Sinh câu trả lời.
-   Gắn thông tin nguồn/citation vào câu trả lời.

------------------------------------------------------------------------

## 5. Kiến trúc hệ thống

``` text
                         ┌───────────────────┐
                         │       User        │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │   React Frontend  │
                         └─────────┬─────────┘
                                   │ REST API
                                   ▼
                    ┌─────────────────────────────┐
                    │          FastAPI            │
                    │       Backend + RAG         │
                    │                             │
                    │ ┌─────────┐ ┌────────────┐ │
                    │ │  Auth   │ │   User     │ │
                    │ ├─────────┤ ├────────────┤ │
                    │ │Document │ │    Chat    │ │
                    │ ├─────────┤ ├────────────┤ │
                    │ │ Admin   │ │ RAG Module │ │
                    │ └─────────┘ └─────┬──────┘ │
                    └───────────────────┼─────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
             ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
             │ PostgreSQL  │     │ Vector DB   │     │     LLM     │
             │             │     │             │     │             │
             │ User        │     │ Embeddings  │     │ Generation  │
             │ Document    │     │ Chunks      │     │             │
             │ Chat        │     │ Metadata    │     │             │
             └─────────────┘     └─────────────┘     └─────────────┘
```

### 5.1. Nguyên tắc kiến trúc

Dự án sử dụng **một ứng dụng FastAPI** thay vì tách riêng backend và RAG
thành hai server.

Các lớp chính:

``` text
API
 ↓
Service
 ↓
RAG Pipeline
 ↓
Embedding / Retrieval / LLM
```

Cách tổ chức này phù hợp với quy mô 2 sinh viên và thời gian 12 tuần,
đồng thời vẫn giữ được sự phân tách giữa API, business logic và AI/RAG.

------------------------------------------------------------------------

## 6. Luồng hỏi đáp RAG

Khi người dùng gửi câu hỏi:

``` text
User Question
      │
      ▼
Normalize Question
      │
      ▼
Generate Query Embedding
      │
      ▼
Vector Similarity Search
      │
      ▼
Retrieve Top-K Chunks
      │
      ▼
Build Prompt
      │
      ├── System Instruction
      ├── User Question
      └── Retrieved Context
              │
              ▼
             LLM
              │
              ▼
       Generated Answer
              │
              ▼
       Attach Citations
              │
              ▼
       Return Response
```

### 6.1. Chi tiết

**Bước 1 - Người dùng đặt câu hỏi**

Ví dụ:

> "Tôi cần những giấy tờ gì để thực hiện thủ tục X?"

**Bước 2 - Tạo embedding cho câu hỏi**

Câu hỏi được chuyển thành vector bằng embedding model.

**Bước 3 - Semantic Search**

Vector câu hỏi được dùng để tìm các chunk có nội dung tương đồng trong
Vector Database.

**Bước 4 - Lấy Top-K kết quả**

Hệ thống lấy một số chunk phù hợp nhất và kèm metadata như:

-   Tên tài liệu
-   Số văn bản
-   Trang
-   Loại tài liệu
-   Ngày ban hành nếu có

**Bước 5 - Xây dựng Prompt**

Context được truy xuất được đưa vào prompt cùng với câu hỏi của người
dùng.

**Bước 6 - LLM sinh câu trả lời**

LLM sử dụng context để tạo câu trả lời.

**Bước 7 - Trả về nguồn**

Hệ thống trả về câu trả lời cùng các tài liệu/chunk liên quan để người
dùng có thể kiểm chứng.

------------------------------------------------------------------------

## 7. Luồng xử lý tài liệu

``` text
Admin
  │
  ▼
React Admin
  │
  │ Upload PDF/DOCX/TXT
  ▼
FastAPI
  │
  ▼
Document Service
  │
  ▼
Document Loader
  │
  ▼
Extract Text
  │
  ▼
Clean Text
  │
  ▼
Chunking
  │
  ▼
Embedding Model
  │
  ▼
Vector Database
  │
  ├── vector
  ├── content
  ├── document_id
  ├── page
  └── metadata
```

### 7.1. Các bước ingestion

1.  Admin upload tài liệu.
2.  Backend lưu thông tin tài liệu.
3.  Loader đọc nội dung.
4.  Cleaner chuẩn hóa nội dung.
5.  Chunker chia tài liệu thành các đoạn.
6.  Embedding service tạo vector.
7.  Vector Database lưu vector và metadata.
8.  Cập nhật trạng thái tài liệu thành `processed`.

------------------------------------------------------------------------

## 8. Cấu trúc thư mục

``` text
local-government-ai-assistant/
│
├── frontend/                         # React Frontend
│   ├── public/                       # File tĩnh
│   └── src/
│       ├── assets/                   # Hình ảnh, icon, font
│       ├── components/               # Component dùng chung
│       ├── layouts/                  # Layout giao diện
│       ├── pages/                    # Các trang chính
│       │   ├── auth/                 # Đăng nhập / đăng ký
│       │   ├── chat/                 # Giao diện trợ lý ảo
│       │   ├── documents/            # Quản lý tài liệu
│       │   ├── admin/                # Quản trị
│       │   └── profile/              # Hồ sơ người dùng
│       ├── services/                 # Gọi REST API
│       │   ├── authService.js
│       │   ├── chatService.js
│       │   ├── documentService.js
│       │   └── userService.js
│       ├── hooks/                    # Custom React Hooks
│       ├── contexts/                 # React Context
│       ├── stores/                   # State management nếu cần
│       ├── routes/                   # React Router
│       ├── utils/                    # Hàm tiện ích
│       ├── constants/                # Hằng số
│       ├── App.jsx                   # Root component
│       └── main.jsx                  # Entry point
│
├── backend/                          # FastAPI Backend
│   ├── app/
│   │   ├── main.py                   # Khởi tạo FastAPI
│   │   ├── api/                      # REST API
│   │   │   ├── auth.py               # API xác thực
│   │   │   ├── users.py              # API người dùng
│   │   │   ├── chat.py               # API chatbot
│   │   │   ├── documents.py          # API tài liệu
│   │   │   └── admin.py              # API quản trị
│   │   │
│   │   ├── core/                     # Cấu hình lõi
│   │   │   ├── config.py             # Environment/config
│   │   │   ├── security.py           # JWT/password hashing
│   │   │   └── dependencies.py       # FastAPI dependencies
│   │   │
│   │   ├── models/                   # Database Models
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── conversation.py
│   │   │   └── message.py
│   │   │
│   │   ├── schemas/                  # Pydantic schemas
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   └── chat.py
│   │   │
│   │   ├── services/                 # Business Logic
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── document_service.py
│   │   │   └── chat_service.py
│   │   │
│   │   ├── repositories/             # Database Access
│   │   │   ├── user_repository.py
│   │   │   ├── document_repository.py
│   │   │   └── conversation_repository.py
│   │   │
│   │   ├── rag/                      # AI/RAG Module
│   │   │   ├── ingestion/
│   │   │   │   ├── loader.py         # Đọc PDF/DOCX/TXT
│   │   │   │   ├── cleaner.py        # Làm sạch nội dung
│   │   │   │   └── chunker.py        # Chia chunks
│   │   │   ├── embedding/
│   │   │   │   └── embedding_service.py
│   │   │   ├── retrieval/
│   │   │   │   ├── vector_store.py
│   │   │   │   └── retriever.py
│   │   │   ├── generation/
│   │   │   │   ├── prompt.py
│   │   │   │   └── llm_service.py
│   │   │   ├── pipeline/
│   │   │   │   └── rag_pipeline.py
│   │   │   └── evaluation/
│   │   │       ├── evaluator.py
│   │   │       └── metrics.py
│   │   │
│   │   └── database/
│   │       ├── connection.py
│   │       └── session.py
│   │
│   ├── requirements.txt              # Python dependencies
│   └── .env                          # Environment variables
│
├── data/
│   ├── raw/                          # Tài liệu gốc
│   ├── processed/                    # Dữ liệu sau xử lý
│   └── evaluation/                   # Dataset đánh giá
│
├── tests/                            # Unit/API/Integration tests
├── docs/                             # Tài liệu dự án
├── docker-compose.yml                # Chạy các service
└── README.md                         # Giới thiệu nhanh
```

------------------------------------------------------------------------

## 9. Các module chính

### 9.1. Authentication

Chức năng:

-   Đăng ký.
-   Đăng nhập.
-   Hash password.
-   JWT access token.
-   Phân quyền.

Vai trò dự kiến:

``` text
USER
ADMIN
```

### 9.2. User Management

Quản lý:

-   User profile.
-   Role.
-   Trạng thái tài khoản.
-   Lịch sử hoạt động cần thiết.

### 9.3. Document Management

Quản lý:

-   Upload tài liệu.
-   Metadata.
-   Trạng thái xử lý.
-   Xóa tài liệu.
-   Trigger ingestion.

Trạng thái tài liệu có thể gồm:

``` text
UPLOADED
PROCESSING
PROCESSED
FAILED
```

### 9.4. Chat Management

Quản lý:

-   Conversation.
-   Message.
-   User question.
-   Assistant answer.
-   Sources.

### 9.5. RAG Pipeline

Pipeline chính:

``` text
Question
  ↓
Embedding
  ↓
Retriever
  ↓
Top-K Chunks
  ↓
Prompt Builder
  ↓
LLM
  ↓
Answer + Sources
```

------------------------------------------------------------------------

## 10. Thiết kế dữ liệu ở mức khái niệm

### User

``` text
User
├── id
├── username
├── email
├── password_hash
├── role
├── status
├── created_at
└── updated_at
```

### Document

``` text
Document
├── id
├── title
├── file_name
├── file_type
├── description
├── status
├── uploaded_by
├── created_at
└── updated_at
```

### Conversation

``` text
Conversation
├── id
├── user_id
├── title
├── created_at
└── updated_at
```

### Message

``` text
Message
├── id
├── conversation_id
├── role
├── content
├── sources
└── created_at
```

### Vector Chunk

Vector Database có thể lưu:

``` text
Chunk
├── id
├── document_id
├── content
├── embedding
├── page
├── chunk_index
└── metadata
```

------------------------------------------------------------------------

## 11. API dự kiến

### Authentication

``` text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
```

### User

``` text
GET /api/users/me
PUT /api/users/me
```

### Chat

``` text
POST /api/chat
GET  /api/chat/conversations
GET  /api/chat/conversations/{conversation_id}
DELETE /api/chat/conversations/{conversation_id}
```

### Documents

``` text
POST   /api/documents
GET    /api/documents
GET    /api/documents/{document_id}
DELETE /api/documents/{document_id}
POST   /api/documents/{document_id}/process
```

### Admin

``` text
GET  /api/admin/users
PUT  /api/admin/users/{user_id}/role
PUT  /api/admin/users/{user_id}/status
```

------------------------------------------------------------------------

## 12. Ví dụ API Chat

### Request

``` json
{
  "conversation_id": 12,
  "question": "Tôi cần chuẩn bị giấy tờ gì cho thủ tục X?"
}
```

### Response

``` json
{
  "answer": "Theo tài liệu được truy xuất, người thực hiện thủ tục cần chuẩn bị ...",
  "sources": [
    {
      "document_id": 5,
      "document_name": "Huong_dan_thu_tuc_X.pdf",
      "page": 3
    }
  ]
}
```

------------------------------------------------------------------------

## 13. Giao diện dự kiến

### 13.1. Trang đăng nhập

``` text
+--------------------------------------+
|          ADMINISTRATIVE AI           |
|                                      |
| Username / Email                     |
| [____________________________]       |
|                                      |
| Password                             |
| [____________________________]       |
|                                      |
|           [ ĐĂNG NHẬP ]              |
+--------------------------------------+
```

### 13.2. Trang Chat

``` text
+------------------------------------------------------+
| Logo | Chat | Lịch sử | Hồ sơ                        |
+------------------------------------------------------+
|                                                      |
|  Người dùng: Tôi cần giấy tờ gì cho thủ tục X?       |
|                                                      |
|  Trợ lý: Theo tài liệu hiện có, bạn cần ...           |
|                                                      |
|  Nguồn:                                             |
|  - Huong_dan_thu_tuc_X.pdf - Trang 3                |
|                                                      |
+------------------------------------------------------+
| Nhập câu hỏi...                         [Gửi]         |
+------------------------------------------------------+
```

### 13.3. Trang quản trị tài liệu

``` text
+------------------------------------------------------+
| Quản lý tài liệu                                     |
+------------------------------------------------------+
| [ Upload tài liệu ]                                  |
+------------------------------------------------------+
| Tên tài liệu       | Loại | Trạng thái | Thao tác   |
|------------------------------------------------------|
| Van_ban_X.pdf      | PDF  | Processed  | Xóa        |
| Huong_dan_Y.docx   | DOCX | Processing | Xóa        |
+------------------------------------------------------+
```

------------------------------------------------------------------------

## 14. Yêu cầu phi chức năng

### Hiệu năng

-   API phản hồi ổn định trong điều kiện demo.
-   Hạn chế truy xuất quá nhiều chunk không cần thiết.
-   Có thể cấu hình `Top-K`.

### Bảo mật

-   Password phải được hash.
-   Sử dụng JWT cho authentication.
-   API quản trị phải kiểm tra quyền.
-   Không lưu API key trực tiếp trong source code.
-   Sử dụng `.env` cho thông tin nhạy cảm.

### Khả năng mở rộng

Thiết kế module hóa để có thể thay đổi:

-   Embedding model.
-   Vector Database.
-   LLM provider.
-   Prompt.
-   Chunking strategy.

mà không phải thay đổi toàn bộ hệ thống.

------------------------------------------------------------------------

## 15. Đánh giá hệ thống

Đánh giá nên được chia thành hai phần.

### 15.1. Đánh giá Retrieval

Kiểm tra hệ thống có tìm được tài liệu/chunk phù hợp hay không.

Có thể sử dụng:

-   Precision@K
-   Recall@K
-   Hit Rate

### 15.2. Đánh giá Answer

Đánh giá:

-   Độ chính xác nội dung.
-   Mức độ bám sát tài liệu.
-   Tính đầy đủ.
-   Tính liên quan.
-   Mức độ có thể kiểm chứng thông qua nguồn.

Có thể xây dựng một bộ câu hỏi kiểm thử gồm:

``` text
Question
Expected Answer
Relevant Document
Relevant Page
```

------------------------------------------------------------------------

## 16. Phân công 2 sinh viên

### Sinh viên 1 - Backend / System

Phụ trách:

``` text
backend/app/api/
backend/app/core/
backend/app/models/
backend/app/schemas/
backend/app/services/
backend/app/repositories/
backend/app/database/
```

Công việc:

-   Thiết kế database.
-   Authentication.
-   JWT.
-   User management.
-   Document management.
-   Conversation management.
-   Chat API.
-   Admin API.
-   Backend testing.
-   Tích hợp frontend/backend.

### Sinh viên 2 - AI/RAG / Frontend

Phụ trách:

``` text
backend/app/rag/
frontend/
data/evaluation/
```

Công việc:

-   Document loader.
-   Text cleaning.
-   Chunking.
-   Embedding.
-   Vector search.
-   RAG pipeline.
-   Prompt.
-   LLM integration.
-   Retrieval evaluation.
-   React UI.
-   Chat interface.
-   Admin document interface.

### Công việc chung

Hai sinh viên cùng thực hiện:

-   Phân tích yêu cầu.
-   Thiết kế kiến trúc.
-   Thiết kế API.
-   Integration testing.
-   Đánh giá hệ thống.
-   Viết báo cáo.
-   Chuẩn bị demo.

------------------------------------------------------------------------

## 17. Kế hoạch 12 tuần

  Tuần   Nội dung
  ------ ---------------------------------------------------
  1      Phân tích yêu cầu, xác định phạm vi, khảo sát RAG
  2      Thiết kế kiến trúc, database, API và UI
  3      Khởi tạo React + FastAPI + PostgreSQL
  4      Authentication, User và Role
  5      Document Management và upload file
  6      Document ingestion, cleaning và chunking
  7      Embedding và Vector Database
  8      Retriever và RAG pipeline
  9      Tích hợp LLM và Chat API
  10     Hoàn thiện React UI và Admin UI
  11     Testing, evaluation và tối ưu
  12     Hoàn thiện hệ thống, báo cáo và demo

------------------------------------------------------------------------

## 18. MVP - Phiên bản tối thiểu

Phiên bản MVP cần có:

``` text
[✓] Đăng nhập
[✓] Upload tài liệu
[✓] Xử lý tài liệu
[✓] Chunking
[✓] Embedding
[✓] Vector Search
[✓] RAG
[✓] LLM
[✓] Chat
[✓] Hiển thị nguồn
[✓] Lịch sử hội thoại
[✓] Quản lý tài liệu
```

Các chức năng nâng cao chỉ thực hiện khi MVP đã ổn định.

------------------------------------------------------------------------

## 19. Các điểm không nằm trong phạm vi

Để phù hợp với thời gian 12 tuần và nhóm 2 sinh viên, dự án không tập
trung vào:

-   Tự động thực hiện toàn bộ thủ tục hành chính.
-   Tự động ra quyết định hành chính.
-   Thay thế cán bộ xử lý hồ sơ.
-   Tích hợp sâu với các hệ thống nghiệp vụ thực tế của cơ quan nhà nước
    nếu không có API/dữ liệu phù hợp.
-   Xử lý mọi loại văn bản hành chính của toàn bộ Việt Nam.
-   Xây dựng một mô hình ngôn ngữ lớn từ đầu.

------------------------------------------------------------------------

## 20. Nguyên tắc hạn chế hallucination

Hệ thống cần được thiết kế để giảm việc LLM tự tạo thông tin không có
trong tài liệu.

Một số nguyên tắc:

1.  Ưu tiên context được truy xuất.
2.  Prompt yêu cầu trả lời dựa trên context.
3.  Nếu không tìm thấy thông tin phù hợp, hệ thống nên thông báo rằng
    chưa có đủ thông tin thay vì tự suy đoán.
4.  Luôn trả về nguồn tài liệu liên quan khi có thể.
5.  Lưu lại câu hỏi, context và câu trả lời phục vụ đánh giá.

------------------------------------------------------------------------

## 21. Kết quả đầu ra dự kiến

Sau khi hoàn thành, dự án dự kiến có:

### Phần mềm

-   Web application React.
-   FastAPI backend.
-   PostgreSQL database.
-   Vector Database.
-   RAG pipeline.
-   LLM integration.
-   Authentication và authorization.
-   Admin document management.

### Tài liệu

-   Tài liệu phân tích yêu cầu.
-   Thiết kế kiến trúc.
-   Thiết kế database.
-   Thiết kế API.
-   Tài liệu RAG pipeline.
-   Bộ dữ liệu đánh giá.
-   Kết quả thử nghiệm.
-   Báo cáo đồ án.
-   Tài liệu hướng dẫn cài đặt và sử dụng.

------------------------------------------------------------------------

## 22. Cách chạy dự án dự kiến

### Backend

``` bash
cd backend

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

### Frontend

``` bash
cd frontend

npm install
npm run dev
```

### Docker

``` bash
docker compose up -d
```

------------------------------------------------------------------------

## 23. Biến môi trường dự kiến

``` env
APP_NAME=local-government-ai-assistant
ENVIRONMENT=development

DATABASE_URL=postgresql://user:password@localhost:5432/assistant_db

JWT_SECRET_KEY=change_me
JWT_ALGORITHM=HS256

LLM_API_KEY=change_me
LLM_MODEL=change_me

EMBEDDING_MODEL=change_me

VECTOR_DB_URL=change_me
```

Không commit `.env` chứa secret thật lên Git repository.

------------------------------------------------------------------------

## 24. Định hướng phát triển

Sau phiên bản đầu tiên, hệ thống có thể mở rộng:

-   Hybrid Search: keyword + semantic search.
-   Reranking.
-   Query rewriting.
-   Conversational RAG.
-   Streaming response.
-   OCR cho tài liệu scan.
-   Phân loại tài liệu tự động.
-   Multilingual support.
-   Dashboard thống kê câu hỏi.
-   Đánh giá RAG tự động.
-   Kết nối nguồn dữ liệu hành chính trực tuyến khi có API phù hợp.

------------------------------------------------------------------------

## 25. Tóm tắt kiến trúc

``` text
                    LOCAL GOVERNMENT AI ASSISTANT
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
          FRONTEND                                  BACKEND
            React                                  FastAPI
              │                                       │
              │                              ┌────────┴────────┐
              │                              │                 │
              │                           REST API           RAG
              │                              │                 │
              │                              │        ┌────────┴────────┐
              │                              │        │                 │
              │                              │    Retrieval         Generation
              │                              │        │                 │
              │                              │    Embedding            LLM
              │                              │        │                 │
              └──────────────────────────────┼────────┼─────────────────┘
                                             │        │
                                             ▼        ▼
                                        PostgreSQL  Vector DB
```

**Kiến trúc cốt lõi:**

> React → FastAPI → RAG Pipeline → Vector Database + LLM

Đây là kiến trúc chính được sử dụng cho phiên bản đồ án 12 tuần.
