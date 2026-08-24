# Contributing to Superstore Platform

This repository contains application, data-engineering, analytics and ML code. A change is
ready for review only when it is traceable, secret-free and verified in the layers it touches.

## 1. Start from a Jira issue

Use the real Jira key in the branch when one exists:

```text
feature/SUP-123-short-outcome
fix/SUP-124-short-outcome
chore/SUP-125-short-outcome
docs/SUP-126-short-outcome
```

Do not mix unrelated features, data fixes and refactors in one branch.

## 2. Never commit local credentials or runtime data

Copy the committed examples and fill only the ignored local files:

```bash
cp RAG_CHATBOT/.env.example RAG_CHATBOT/.env
cp RAG_CHATBOT/frontend/.env.example RAG_CHATBOT/frontend/.env.local
cp data_platform/.env.example data_platform/.env
cp data_platform/superstore_db/.dbt/profiles.yml.example \
  data_platform/superstore_db/.dbt/profiles.yml
cp odoo_dev/odoo.conf.example odoo_dev/odoo.conf
```

Before staging files, run:

```bash
python3 scripts/check_repo_hygiene.py
git diff --check
```

## 3. Commit by outcome

Use small commits that can be reviewed independently:

```text
SUP-123 feat: add customer order status endpoint
SUP-123 test: cover unauthorized order access
SUP-123 docs: record customer order contract
```

The historical STEP 2 baseline is the one exception: it captures the already-integrated
working tree before new feature work. All later work returns to small commits.

## 4. Verify the changed layers

```bash
make verify-hygiene
make test
make frontend-check
make compose-check
make dbt-parse
```

`make verify` runs all offline checks. It does not start Docker services or connect to
Snowflake, Odoo, Qdrant, Redis or an LLM.

## 5. Open a pull request

Fill every relevant section in the pull-request template. Link Jira and Confluence, attach
test evidence, and state what is intentionally outside the change. Do not push directly to
`main` after branch protection is enabled.
