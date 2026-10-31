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
- [ ] Prometheus starts successfully and its targets are `UP`.
- [ ] FastAPI `/metrics` is reachable from Prometheus over the internal Docker network.
- [ ] Redis Exporter exposes Redis metrics successfully.
- [ ] Node Exporter exposes VPS host metrics successfully.
- [ ] Alloy can read the mounted FastAPI and Nginx log files.
- [ ] Loki receives logs from Alloy and supports log queries.
- [ ] MinIO bucket for Loki log storage exists and is accessible.
- [ ] Grafana successfully connects to Prometheus and Loki datasources.
- [ ] Grafana dashboards display expected metrics and logs.
- [ ] SSH tunnel provides access to Grafana and Prometheus.
- [ ] Monitoring ports are not publicly accessible.
- [ ] Monitoring containers and persistent volumes survive a container restart.

## Safety checklist

- [ ] No `.env`, password, API key, token, customer database or runtime data is committed
- [ ] No unrelated refactor is mixed into this change
- [ ] Public/internal/customer authorization boundaries remain explicit
- [ ] Documentation and `project_context.md` are updated when architecture or status changed
- [ ] Rollback or migration impact is described when data/configuration changed
- [ ] Monitoring images are pinned by digest
- [ ] Monitoring ports are not exposed publicly
- [ ] Grafana and MinIO credentials are stored in protected runtime configuration
- [ ] Loki and MinIO communicate through the internal Docker network
- [ ] Prometheus, Loki, Grafana and MinIO use persistent storage where required
- [ ] Alloy has read-only access to application and Nginx log directories
- [ ] Log retention and storage usage limits are configured

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

## CD Superstore Production

| Case ID | Acceptance Criterion                                                                                            | Test / control                                           | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ---- | ------- | ------------------------- | ------ |
| CD-01   | Chỉ deploy commit thuộc repository hiện tại, đã qua Quality Gate thành công trên `main` và vẫn là HEAD mới nhất | `validate-source` — source validation                    | Có   |         |                           |        |
| CD-02   | API Docker image được build cho `linux/amd64`, publish lên GHCR theo release SHA và pin bằng SHA256 digest      | `publish-api` — build and publish immutable image        | Có   |         |                           |        |
| CD-03   | VPS nhận đúng release archive, xác thực SSH và triển khai API bằng đúng release SHA và image digest             | `deploy-production` — SSH transfer and VPS deployment    | Có   |         |                           |        |
| CD-04   | Next.js frontend được build và deploy thành công lên Vercel Production                                          | `deploy-production` — Vercel deployment                  | Có   |         |                           |        |
| CD-05   | Production website, public health và CFO authentication/dashboard authorization hoạt động đúng                  | `deploy-production` — `smoke_public.py`                  | Có   |         |                           |        |
| CD-06   | Deployment chạy tuần tự, sử dụng GitHub Production Environment và dọn SSH credentials kể cả khi thất bại        | Workflow concurrency, `environment: production`, cleanup | Có   |         |                           |        |

## Production API smoke test quality gate

| Case ID   | Acceptance Criterion                                                                                           | Test / control                         | Code | Kết quả | Commit / run / bằng chứng | Defect |
| --------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ---- | ------- | ------------------------- | ------ |
| DEPLOY-01 | Public health endpoint trả `200`, `status=ok`, `api=up`                                                        | `smoke_public.py` — Public health      | Có   |         |                           |        |
| DEPLOY-02 | Anonymous access vào `/api/internal/staff/me` trước login trả `401`                                            | `smoke_public.py` — Anonymous access   | Có   |         |                           |        |
| DEPLOY-03 | CFO login thành công; cookie có `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`                                 | `smoke_public.py` — CFO login / cookie | Có   |         |                           |        |
| DEPLOY-04 | KPI response chứa đầy đủ các field bắt buộc theo API contract                                                  | `smoke_public.py` — KPI contract       | Có   |         |                           |        |
| DEPLOY-05 | CFO không được truy cập `by-category`; endpoint không xuất hiện trong index và gọi trực tiếp trả `403`         | `smoke_public.py` — Dashboard RBAC     | Có   |         |                           |        |
| DEPLOY-06 | Logout thành công; session/cookie bị vô hiệu hóa và truy cập staff endpoint sau logout không còn được xác thực | `smoke_public.py` — Logout             | Có   |         |                           |        |
