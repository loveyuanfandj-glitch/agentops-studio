# Architecture

## Components

### Operations console

The Next.js/Vinext client is an operator surface, not a chat mockup. It presents tenant-level SLOs, costs, traces, tool schemas, and guard policies. `NEXT_PUBLIC_API_URL` activates the FastAPI-backed playground; otherwise the console uses the same deterministic showcase data for a zero-setup portfolio preview.

### API layer

FastAPI owns request validation, tenant resolution, conversation lifecycle, run lookup, and usage metrics. Every tenant-scoped endpoint resolves `X-Tenant-ID` before repository access. In a commercial deployment, the header should come from a trusted gateway or signed identity claim rather than directly from the browser.

### Orchestrator

`AgentOrchestrator` is the control plane. It:

1. persists the user message and creates a run;
2. calls the provider with conversation history and strict tool schemas;
3. appends the model's complete output to working context;
4. validates and executes requested tools in order;
5. returns each result with its original `call_id`;
6. repeats until the provider returns final text or a guard fires;
7. stores every model/tool step, usage counter, cost estimate, status, and latency.

### Provider boundary

`AgentProvider` deliberately exposes only `respond(input_items, tools, instructions)`. `OpenAIProvider` maps that contract onto the Responses API. `MockProvider` produces the same orchestration shape deterministically, which keeps tests fast and the public demo credential-free.

### Tool registry

Each tool combines a Pydantic input type, a description, and an async handler. The input type is exported as a strict JSON Schema. The registry is also the execution boundary for timeouts, retries, validation errors, unknown tools, and normalized integration failures.

### Persistence

The relational model is optimized for trace reconstruction:

```text
Tenant
  ├── Conversation
  │     ├── Message
  │     └── AgentRun
  │           └── RunStep
  └── AgentRun (for tenant-wide metrics)
```

`RunStep.arguments` and `RunStep.output` use JSON/JSONB, while searchable operational dimensions remain typed columns and indexed.

## Failure model

- **Tool validation/execution failure:** stored on the step and returned to the model as structured data.
- **Provider failure:** run ends as `failed` with a stable error code.
- **Repeated call / step / budget guard:** run ends as `guarded`, distinct from infrastructure failure.
- **Total deadline:** run ends as `failed:run_timeout`.
- **Unexpected exception:** logged with run and tenant context and persisted as `internal_error`.

## Production extensions

The demo keeps authentication and domain tools intentionally small. A production rollout should add signed tenant claims, field-level redaction, per-tool authorization, a queue for long-running operations, rate limits, provider failover, encrypted secrets, and trace retention policies.
