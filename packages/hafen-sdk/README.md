# hafen-sdk

Python client for the [Hafen](https://hafen.ai) migration platform.

Targets self-hosted Hafen installs (the product); calls the REST API
at `/api/v1/*`. No direct DB access, no cloud-specific endpoints.

## Install

```bash
pip install hafen-sdk
```

## Quick start

```python
from hafen_sdk import HafenClient

# Log in with credentials (auto-fetches a bearer token):
client = HafenClient(
    base_url="https://hafen.your-company.internal",
    email="admin@your-company.com",
    password="…",
)

# Or skip login and use an existing token:
client = HafenClient(base_url="…", access_token="eyJ…")

# Create, run, and poll a migration:
m = client.create_migration(
    name="nightly-staging-refresh",
    source_url="oracle://hr_user:…@oracle-prod:1521/ORCL",
    target_url="postgresql+psycopg://hafen:…@pg-stage:5432/stage",
    source_schema="HR",
    target_schema="hr",
    batch_size=10_000,
    create_tables=True,
)
client.run_migration(m.id)
progress = client.get_progress(m.id)

# Schedule it nightly at 2am ET:
client.upsert_schedule(
    m.id,
    name="nightly",
    cron_expr="0 2 * * *",
    timezone="America/New_York",
    enabled=True,
)

# Redact PII before it lands in staging:
client.put_masking(m.id, rules={
    "HR.EMPLOYEES": {
        "EMAIL":      {"strategy": "hash"},
        "SSN":        {"strategy": "partial", "keep_first": 0, "keep_last": 4},
        "MANAGER_ID": {"strategy": "null"},
    }
})

# Fire a webhook on each run:
client.create_webhook(
    name="ops-slack",
    url="https://hooks.slack.com/…",
    secret="shared-hmac-secret",
    events=["migration.completed", "migration.failed"],
)
```

## Errors

Every 4xx from the API raises a typed exception you can catch:

```python
from hafen_sdk import AuthError, LicenseError, NotFoundError, ValidationError

try:
    client.run_migration(some_id)
except LicenseError as e:
    print("Pro license needed for this feature:", e.detail)
except NotFoundError:
    print("migration doesn't exist")
```

## Development

```bash
cd packages/hafen-sdk
pip install -e '.[dev]'
pytest
```
