RAG := RAG_CHATBOT
DATA := data_platform
FRONTEND := $(RAG)/frontend
DBT_IN_AIRFLOW := cd "$(DATA)" && docker compose exec -T -w /opt/airflow/superstore_db airflow-scheduler /home/airflow/dbt-venv/bin/dbt
E2E_ARGS ?=

GREEN := \033[32m
RESET := \033[0m

.PHONY: python-syntax verify-hygiene pipeline-contract test-auth test-dashboard test-integration test-operations backend-check frontend-check frontend-e2e-up frontend-e2e compose-check dbt-parse dbt-check-account dbt-test-staging dbt-test-silver dbt-test-gold dbt-test-mart dbt-test-singular dbt-tests verify


# Kiểm tra Python syntax
# - Bỏ qua file đã xóa trong worktree nhưng Git vẫn liệt kê trước khi commit

python-syntax:
	git ls-files -co --exclude-standard -z '*.py' \
	| xargs -0 -n 1 sh -c 'test -f "$$1" || exit 0; python3 -m py_compile "$$1"' _
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


# Kiểm tra backend bằng virtual environment của RAG_CHATBOT

test-auth:
	cd "$(RAG)" && .venv/bin/python -m pytest tests/auth -q

test-dashboard:
	cd "$(RAG)" && .venv/bin/python -m pytest tests/dashboard -q

test-integration:
	cd "$(RAG)" && .venv/bin/python -m pytest tests/integration -q

test-operations:
	cd "$(RAG)" && .venv/bin/python -m pytest tests/operations -q


backend-check:
	cd "$(RAG)" && .venv/bin/python -m pytest tests/ -q
	@printf "$(GREEN)✓ Backend tests passed$(RESET)\n"


# Kiểm tra frontend Next.js
# 1. ESLint
# 2. TypeScript
# 3. Production build

frontend-check:
	cd "$(FRONTEND)" && \
	npm ci && \
	npm run lint && \
	npm run typecheck && \
	npm run build
	@printf "$(GREEN)✓ Frontend checks passed$(RESET)\n"


# E2E local dùng Docker development và staff marketing đã được tạo một lần

frontend-e2e-up:
	cd "$(DATA)" && docker compose --profile app config --quiet
	cd "$(DATA)" && docker compose --profile app up -d --build --force-recreate api frontend
	cd "$(DATA)" && docker compose --profile app ps api frontend

frontend-e2e:
	@test -f "$(FRONTEND)/e2e-test-env" || { echo "Missing $(FRONTEND)/e2e-test-env"; exit 1; }
	$(MAKE) frontend-e2e-up
	cd "$(FRONTEND)" && npm ci && npx playwright install chromium && npm run test:e2e:docker -- $(E2E_ARGS)
	@printf "$(GREEN)✓ Frontend Docker E2E passed$(RESET)\n"


# Kiểm tra Docker Compose
# - Parse compose
# - Kiểm tra syntax/config/service/volume/network/environment
# - Không khởi động container

compose-check:
	cd "$(DATA)" && docker compose config --quiet
	@printf "$(GREEN)✓ Docker Compose config passed$(RESET)\n"


# Kiểm tra dbt project
# - Load environment variables từ data_platform/.env
# - Resolve dbt dependencies
# - Parse models, sources, macros, YAML và profile
# - Không chạy transformation thật lên Snowflake

dbt-parse:
	cd "$(DATA)/superstore_db" && \
	set -a && \
	. ../.env && \
	set +a && \
	dbt deps --quiet && \
	dbt parse --no-partial-parse --profiles-dir .dbt
	@printf "$(GREEN)✓ dbt parse passed$(RESET)\n"


# Test dữ liệu Snowflake thật sau khi pipeline đã nạp đủ các layer
# - Dùng cùng dbt venv và selectors với Airflow; không chạy trong PR CI

dbt-check-account:
	@cd "$(DATA)" && \
	expected=$$(sed -n 's/^SNOWFLAKE_ACCOUNT=//p' .env | tail -n 1) && \
	actual=$$(docker compose exec -T airflow-scheduler printenv SNOWFLAKE_ACCOUNT) && \
	if [ -z "$$expected" ] || [ "$$expected" != "$$actual" ]; then \
		echo "Snowflake account mismatch: .env=$$expected, airflow-scheduler=$$actual"; \
		echo "Recreate airflow-scheduler after changing data_platform/.env."; \
		exit 1; \
	fi

dbt-test-staging: dbt-check-account
	$(DBT_IN_AIRFLOW) test --select staging --indirect-selection cautious --profiles-dir .dbt

dbt-test-snapshot: dbt-check-account
	$(DBT_IN_AIRFLOW) test --select resource_type:snapshot --indirect-selection cautious --profiles-dir .dbt

dbt-test-silver: dbt-check-account
	$(DBT_IN_AIRFLOW) test --select silver --indirect-selection cautious --profiles-dir .dbt

dbt-test-gold: dbt-check-account
	$(DBT_IN_AIRFLOW) test --select gold --indirect-selection cautious --profiles-dir .dbt

dbt-test-mart: dbt-check-account
	$(DBT_IN_AIRFLOW) test --select mart --indirect-selection cautious --profiles-dir .dbt

dbt-test-singular: dbt-check-account
	$(DBT_IN_AIRFLOW) test --select test_type:singular --profiles-dir .dbt

dbt-tests:
	$(MAKE) dbt-test-staging
	$(MAKE) dbt-test-snapshot
	$(MAKE) dbt-test-silver
	$(MAKE) dbt-test-gold
	$(MAKE) dbt-test-mart
	$(MAKE) dbt-test-singular
	@printf "$(GREEN)✓ All dbt data tests passed$(RESET)\n"


# Local quality gate trước commit: backend, E2E và dbt data tests đều bắt buộc


verify:
	$(MAKE) verify-hygiene
	$(MAKE) python-syntax
	$(MAKE) backend-check
	$(MAKE) frontend-check
	$(MAKE) compose-check
	$(MAKE) pipeline-contract
	$(MAKE) dbt-parse
	$(MAKE) frontend-e2e
	$(MAKE) dbt-tests
	@printf "\n$(GREEN)✓ All quality checks passed$(RESET)\n"
