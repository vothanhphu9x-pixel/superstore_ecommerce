RAG := RAG_CHATBOT
DATA := data_platform

.PHONY: verify-hygiene test frontend-check compose-check dbt-parse verify

# Kiểm tra Git repository hygiene:
# - Không track .env, secret, local config, runtime artifact
# - Các file .env.example / *.example bắt buộc phải tồn tại
# - Kiểm tra whitespace lỗi trong Git diff
verify-hygiene:
	python3 scripts/check_repo_hygiene.py
	git diff --check

# Kiểm tra backend Python:
# - Chạy toàn bộ pytest trong RAG_CHATBOT/tests/
# - Dùng Python virtual environment của backend
test:
	cd "$(RAG)" && env/bin/python -m pytest tests/ -v

# Kiểm tra frontend Next.js:
# 1. ESLint: lỗi code/style
# 2. TypeScript: lỗi type
# 3. Production build: xác nhận app build được
frontend-check:
	cd "$(RAG)/frontend" && npm run lint && npx tsc --noEmit && npm run build

# Kiểm tra Docker Compose:
# - Parse file compose
# - Kiểm tra syntax/config/service/volume/network/environment hợp lệ
# - Không khởi động container
compose-check:
	cd "$(DATA)" && docker compose config --quiet

# Kiểm tra dbt project:
# - Load environment variables từ Data_warehouse/.env
# - Cài/resolve dbt package dependencies
# - Parse toàn bộ models, sources, macros, YAML và profile
# - Không chạy transformation thật lên Snowflake
dbt-parse:
	cd "$(DATA)/superstore_db" && set -a && . ../Data_warehouse/.env && set +a && \
		dbt deps --quiet && dbt parse --no-partial-parse --profiles-dir .dbt

# Chạy toàn bộ quality gate trước commit/PR/merge:
verify: verify-hygiene test frontend-check compose-check dbt-parse