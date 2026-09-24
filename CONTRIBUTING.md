# Contributing to Superstore Platform

This repository contains application, data-engineering, analytics and ML code. A change is
ready for review only when it is traceable, secret-free and verified in the layers it touches.

## 1. Sync the local `main` branch

Update the local baseline before creating a working branch:

```bash
git switch main
git pull origin main
```

Resolve or preserve any local changes before switching branches. Do not overwrite another
contributor's work.

If the working tree contains unfinished changes, temporarily store them before updating
`main`, then restore them on the original working branch:

```bash
git stash push -u -m "temporary work before updating main"
git switch main
git pull origin main
git switch <working_branch>
git stash pop
```

Do not run `git stash pop` while still on `main`; doing so applies feature changes directly
to the local `main` branch. Resolve any conflicts reported by `git stash pop` before
continuing.

## 2. Start from a Jira issue

Use the real Jira key in the branch when one exists:

```text
feature/SUP-123-short-outcome
fix/SUP-124-short-outcome
chore/SUP-125-short-outcome
docs/SUP-126-short-outcome
```

Do not mix unrelated features, data fixes and refactors in one branch.

## 3. Never commit local credentials or runtime data

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

To verify why a local file is ignored:

```bash
git check-ignore -v <file_name>
```

## 4. Review Git changes before committing

Check unstaged changes first:

```bash
git status --short
git diff --stat
git diff --check
```

After `git add`, check exactly what will be committed:

```bash
git diff --cached --stat
git diff --cached --check
```

- `git status --short`: lists modified, staged, untracked and deleted files.
- `git diff --stat`: summarizes unstaged changes.
- `git diff --cached --stat`: summarizes staged changes.
- `git diff --check` and `git diff --cached --check`: detect whitespace errors in unstaged
  and staged changes respectively.
- `git check-ignore -v <file_name>`: shows the ignore rule and file that matched it.

## 5. Verify the changed layers

```bash
make python-syntax
make verify-hygiene
make pipeline-contract
make test
make frontend-check
make compose-check
make dbt-parse
```

check build container

```bash
cd RAG_CHATBOT
docker build -t superstore-api:step5 .
```

Compile the complete dbt project using the dedicated dbt environment in Airflow:

```bash
cd data_platform
docker compose up -d <service_name>
docker compose exec -T \
  -w /opt/airflow/superstore_db \
  airflow-scheduler \
  /home/airflow/dbt-venv/bin/dbt compile --profiles-dir .dbt
```

`docker compose config --quiet` returns no output when the Compose configuration is valid.
`dbt compile` validates Jinja, `ref()`, macros, SQL generation and the dbt dependency graph;
the Airflow containers must be running for this command.

`make verify` runs all offline checks. It does not start Docker services or connect to
Snowflake, Odoo, Qdrant, Redis or an LLM.

## 6. Commit by outcome

Use small commits that can be reviewed independently:

```text
SUP-123 feat: add customer order status endpoint
SUP-123 test: cover unauthorized order access
SUP-123 docs: record customer order contract
```

Run the commands from the repository root:

```bash
# Stage new, modified and deleted files
git add .

# Review exactly what will be committed
git status --short
git diff --cached --stat
git diff --cached --check

# Create the commit
git commit -m "SUP-123 feat: describe the completed outcome"

# First push: create the remote branch and configure its upstream
git push -u origin "$(git branch --show-current)"
```

After the upstream has been configured, later commits only require:

```bash
git add .
git commit -m "SUP-123 fix: describe the corrected outcome"
git push -u origin ...
```

Replace `SUP-123` and the message with the real Jira key and completed outcome. Never run
`git commit` when `git diff --cached --check` reports an error.

The historical STEP 2 baseline is the one exception: it captures the already-integrated
working tree before new feature work. All later work returns to small commits.

## 7. Open a pull request

Fill every relevant section in the pull-request template. Link Jira and Confluence, attach
test evidence, and state what is intentionally outside the change. Do not push directly to
`main` after branch protection is enabled.
