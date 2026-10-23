## Jira / Confluence

- Jira issue:
- Confluence design or requirement:

## Outcome

<!-- Describe the user or system outcome, not only the files changed. -->

## Scope

- Included:
- Explicitly excluded:

## Input / output or contract changes

- Input:
- Output:
- API, data model, cookie/session or permission impact:

## Verification

- [ ] `python scripts/check_repo_hygiene.py`
- [ ] Backend tests pass when backend changed
- [ ] Frontend lint, type-check and build pass when frontend changed
- [ ] `docker compose config --quiet` passes when infrastructure changed
- [ ] `python3 scripts/check_de_pipeline_contract.py`
- [ ] `dbt parse` passes when dbt changed
- [ ] Manual or Postman evidence is attached when an API contract changed

## Safety checklist

- [ ] No `.env`, password, API key, token, customer database or runtime data is committed
- [ ] No unrelated refactor is mixed into this change
- [ ] Public/internal/customer authorization boundaries remain explicit
- [ ] Documentation and `project_context.md` are updated when architecture or status changed
- [ ] Rollback or migration impact is described when data/configuration changed

## CI quality gate

| Jira Story | Case ID | Acceptance Criterion                                          | Test / control                                 | Code          | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | ------------------------------------------------------------- | ---------------------------------------------- | ------------- | ------- | ------------------------- | ------ |
|            | CI-01   | Repository hygiene pass                                       | `quality.yml` — job `hygiene`                  | Có            |         |                           |        |
|            | CI-02   | Python files được track biên dịch cú pháp thành công          | `quality.yml` — job `python-syntax`            | Có            |         |                           |        |
|            | CI-03   | Backend pytest pass; FastAPI khởi động và `/health/live` pass | `quality.yml` — job `backend`                  | Có            |         |                           |        |
|            | CI-04   | Frontend `npm ci`, lint, type-check và build pass             | `quality.yml` — job `frontend`                 | Có            |         |                           |        |
|            | CI-05   | E2E dùng credential/SQLite tạm, chạy thật và pass, không skip | `quality.yml` — step `Run frontend E2E`        | Có            |         |                           |        |
|            | CI-06   | Compose, DE contract và dbt parse pass                        | `quality.yml` — job `configuration`            | Có            |         |                           |        |
|            | CI-07   | Job bắt buộc fail thì PR không được merge                     | GitHub branch ruleset / required status checks | Chưa xác minh |         |                           |        |
