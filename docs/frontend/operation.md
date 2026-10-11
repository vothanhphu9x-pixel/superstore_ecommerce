# Frontend Operations

## 1. Cấu hình và chạy

Chuẩn bị `RAG_CHATBOT/.env` cho FastAPI và tạo staff theo
[API operation](../API/operation.md). Staff tạo bằng CLI local nằm trong
`RAG_CHATBOT/data`; staff tạo trong container nằm ở Docker volume
`staff_auth_data` — hai nơi **không dùng chung** tài khoản.

`RAG_CHATBOT/frontend/.env.local` chỉ dành cho Next.js server:

```dotenv
INTERNAL_API_URL=http://localhost:8000
API_KEY=REPLACE_WITH_FASTAPI_API_KEY
Frontend_Origin=http://localhost:3000
```

`API_KEY` phải khớp với API; khi triển khai HTTPS, đặt
`STAFF_COOKIE_SECURE=true` trong `RAG_CHATBOT/.env`. Xem các bước xác minh
đăng nhập, BFF và dashboard tại [Test Operations](../tests/operation.md).

### 1.1. Chạy local

Cài dependencies một lần trong `RAG_CHATBOT/frontend`: `npm ci`. Sau đó mở ba
terminal:

```bash
# Terminal 1 — Redis
cd data_platform
docker compose up -d redis
```

```bash
# Terminal 2 — FastAPI
cd RAG_CHATBOT
source .venv/bin/activate
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Terminal 3 — Next.js
cd RAG_CHATBOT/frontend
npm run dev
```

### 1.2. Chạy bằng Docker Compose

Đặt `INTERNAL_API_URL=http://api:8000` trong `frontend/.env.local`, rồi chạy
từ root repository:

```bash
cd data_platform
docker compose --profile app up -d --build api frontend
docker compose ps api frontend
```

Compose cấp biến cho frontend qua `frontend/.env.local`, cho API qua
`RAG_CHATBOT/.env`; không cần `set -a`. Nếu chỉ sửa frontend, build và tạo lại
riêng service này:

```bash
docker compose --profile app up -d --build --no-deps --force-recreate frontend
```

Lệnh `docker compose up -d --build` **không có `--profile app`** sẽ bỏ qua API và
frontend. Với cả hai cách chạy, mở `http://localhost:3000/dashboard`.

Kiến trúc BFF được mô tả trong
[System Architecture Lineage](system_architecutre_lineage.md); các bước kiểm tra
nằm trong [Test Operations](../tests/operation.md).
