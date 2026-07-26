# Operations runbook

## First checks

1. Call `GET /health`; a non-200 response usually indicates database connectivity or migration failure.
2. Find the run in `GET /api/v1/runs/{run_id}` using the correct `X-Tenant-ID`.
3. Check `status`, `error_code`, and `guardrail_reason` before reading individual steps.
4. Inspect the last completed model or tool step and its duration.
5. Correlate structured logs by `run_id` and `tenant_id`; inspect OTLP traces if configured.

## Run is `guarded`

- `maximum ... model steps reached`: inspect whether the model is alternating tools without converging. Improve tool descriptions or add a more specific orchestration policy before raising the limit.
- `repeated tool call detected`: compare canonical arguments and the previous tool output. The tool may be returning insufficient or ambiguous information.
- `estimated run cost exceeded`: choose a lower-cost model, reduce history, use caching, or split the workflow. Raise the cap only after measuring expected task value.

## Run is `failed`

- `provider_request_failed`: confirm API credentials, provider status, model access, and outbound network access.
- `invalid_tool_arguments`: preserve the provider response and compare it with the current tool schema.
- `run_timeout`: identify the slowest step, then optimize or move the operation to an asynchronous job.
- `internal_error`: inspect structured logs and reproduce with the deterministic provider where possible.

## Tool step is `failed`

Tool errors include a stable code. Validation failures are not retried. Timeouts and unknown integration errors can retry according to `TOOL_RETRY_ATTEMPTS`; the final structured failure is returned to the model so it can choose another action.

## Database migrations

```bash
cd backend
alembic upgrade head
alembic current
alembic check
```

Never run application traffic against a partially migrated schema. Docker starts the API only after `alembic upgrade head` succeeds.

## Switching providers

```bash
export AGENT_PROVIDER=openai
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-5.6-terra
```

Restart the API and confirm the provider through a low-risk playground request. Keep `OPENAI_STORE_RESPONSES=false` unless your data policy explicitly permits provider-side storage.
