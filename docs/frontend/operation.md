# Frontend Operations

## 1. Cấu hình

Next.js server đọc `RAG_CHATBOT/frontend/.env.local` khi chạy local hoặc Docker:

```dotenv
INTERNAL_API_URL=http://localhost:8000
API_KEY=CHANGE_ME_SAME_VALUE_AS_RAG_CHATBOT_API_KEY
Frontend_Origin=http://localhost:3000
```

`API_KEY` phải trùng `API_KEY` của FastAPI. `Frontend_Origin` phải bằng chính xác
origin browser đang dùng. Khi chạy Docker Compose, đổi upstream thành
`INTERNAL_API_URL=http://api:8000`. Không đặt các biến này thành `NEXT_PUBLIC_*`.

FastAPI cần cấu hình và staff account trước; xem [API Operations](../API/operation.md).

## 2. Chạy local

Trong `RAG_CHATBOT/frontend`, cài dependencies một lần:

```bash
npm ci
```

Mở ba terminal:

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

Mở <http://localhost:3000/login> hoặc <http://localhost:3000/dashboard>.
Test commands nằm trong [Test Operations](../tests/operation.md).

## 3. Chạy bằng Docker Compose

Trong `RAG_CHATBOT/frontend/.env.local`, đặt `INTERNAL_API_URL=http://api:8000`.
Compose nạp Next env từ file đó và API env từ `RAG_CHATBOT/.env`:

```bash
cd data_platform
docker compose --profile app up -d --build api frontend
docker compose ps api frontend redis
```

Staff DB nằm trong named volume `staff_auth_data`; log API nằm trong
`superstore_api_logs`. Hai volume giữ dữ liệu khi recreate container.

Chỉ build lại frontend khi cần:

```bash
docker compose --profile app up -d --build --no-deps --force-recreate frontend
```

Production Vercel deploy tự động sau Quality Gate; không dùng Compose production.
Xem [Deploy Operations](../deploy/operation.md).

## 4. Tài liệu liên quan

- Luồng và security boundary: [system_architecture_lineage.md](system_architecture_lineage.md)
- Khoanh vùng lỗi: [error_tracing.md](error_tracing.md)
- Chạy test: [Test Operations](../tests/operation.md)
