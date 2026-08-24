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
- [ ] `dbt parse` passes when dbt changed
- [ ] Manual or Postman evidence is attached when an API contract changed

## Safety checklist

- [ ] No `.env`, password, API key, token, customer database or runtime data is committed
- [ ] No unrelated refactor is mixed into this change
- [ ] Public/internal/customer authorization boundaries remain explicit
- [ ] Documentation and `project_context.md` are updated when architecture or status changed
- [ ] Rollback or migration impact is described when data/configuration changed
