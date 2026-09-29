RAG := RAG_CHATBOT
DATA := data_platform

GREEN := \033[32m
RESET := \033[0m

.PHONY: python-syntax verify-hygiene pipeline-contract test frontend-check compose-check dbt-parse verify


# Kiểm tra Python syntax

python-syntax:
	git ls-files -co --exclude-standard -z '*.py' \
	| xargs -0 python3 -m py_compile
	@printf "$(GREEN)✓ Python syntax check passed$(RESET)\n"


# Kiểm tra Git repository hygiene
# - Không track .env, secret, local config, runtime artifact
# - Các file .env.example / *.example bắt buộc phải tồn tại
# - Kiểm tra whitespace lỗi trong Git diff

verify-hygiene:
	python3 scripts/check_repo_hygiene.py
	git diff --check
	@printf "$(GREEN)✓ Repository hygiene passed$(RESET)\n"


# Kiểm tra DE pipeline contract

pipeline-contract:
	python3 scripts/check_de_pipeline_contract.py
	@printf "$(GREEN)✓ DE pipeline contract passed$(RESET)\n"


# Kiểm tra backend Python
# - Chạy toàn bộ pytest trong RAG_CHATBOT/tests/
# - Dùng Python virtual environment của backend

test:
	cd "$(RAG)" && .venv/bin/python -m pytest tests/ -v
	@printf "$(GREEN)✓ Backend tests passed$(RESET)\n"


# Kiểm tra frontend Next.js
# 1. ESLint
# 2. TypeScript
# 3. Production build

frontend-check:
	cd "$(RAG)/frontend" && \
	npm run lint && \
	npx tsc --noEmit && \
	npm run build
	@printf "$(GREEN)✓ Frontend checks passed$(RESET)\n"


# Kiểm tra Docker Compose
# - Parse compose
# - Kiểm tra syntax/config/service/volume/network/environment
# - Không khởi động container

compose-check:
	cd "$(DATA)" && docker compose config --quiet
	@printf "$(GREEN)✓ Docker Compose config passed$(RESET)\n"


# Kiểm tra dbt project
# - Load environment variables từ Data_warehouse/.env
# - Resolve dbt dependencies
# - Parse models, sources, macros, YAML và profile
# - Không chạy transformation thật lên Snowflake

dbt-parse:
	cd "$(DATA)/superstore_db" && \
	set -a && \
	. ../Data_warehouse/.env && \
	set +a && \
	dbt deps --quiet && \
	dbt parse --no-partial-parse --profiles-dir .dbt
	@printf "$(GREEN)✓ dbt parse passed$(RESET)\n"


# Chạy toàn bộ quality gate trước commit / PR / merge

verify: python-syntax verify-hygiene pipeline-contract test frontend-check compose-check dbt-parse
	@printf "\n$(GREEN)✓ All quality checks passed$(RESET)\n"