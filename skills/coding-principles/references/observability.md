# Observability — industry conventions

Language-agnostic telemetry practices. Operationalizes the parent skill's **observability mantra** in industry-standard terms. Applies whenever the code under change runs in production and someone will need to debug it without a debugger attached.

Scope boundary: this file covers observability *as code* — what to instrument and how. It does *not* cover observability *as infrastructure* (dashboard setup, alerting rules, SLO definitions, on-call) — that belongs in an ops/SRE skill, not here.

## The three signals (OpenTelemetry model)

[OpenTelemetry (OTel)](https://opentelemetry.io/) is the cross-language industry standard. It unifies three signals behind one SDK and wire format, so you instrument once and export anywhere (Jaeger, Prometheus, Grafana, Datadog, Honeycomb, etc.).

- **Traces** — the path of a request across functions and services. A trace is a tree of **spans**; each span has a name, start/end time, attributes, and a parent. This is how you answer "why was this request slow?".
- **Metrics** — aggregated numbers over time (counters, gauges, histograms). This is how you answer "what's the p99 latency?" / "what's the error rate?".
- **Logs** — discrete timestamped events with structured fields. This is how you answer "what exactly happened to *this* request?".

The power is correlation: a log line carries the `trace_id`, so from a metric spike you find the trace, and from the trace you find the logs.

## Structured logging

- **Structured, not string-concatenated.** `logger.info("order placed", order_id=..., user_id=..., amount_cents=...)` — fields, not `f"order {id} placed for {user}"`. Structured logs are queryable; prose logs are not.
- **Log identifiers and shapes, never secrets** (principle 13) — `user_id`, `request_id`, `payload_size`; never tokens, passwords, full request bodies.
- **Include the trace/correlation ID** on every log line in a request path so logs join to traces.
- **Levels mean things**: `ERROR` = needs attention; `WARN` = unexpected but handled; `INFO` = significant business events; `DEBUG` = developer detail. Don't log at `ERROR` for handled conditions — it trains responders to ignore errors.
- **Log at the edges**, not the interior (observability mantra) — entry, exit, error of a unit of work; not every line of the algorithm.

## Tracing

- **Span the boundaries**: incoming request, outgoing call (HTTP / DB / cache / queue), significant compute. Not every function.
- **Propagate context** across service and async boundaries — OTel context propagation (W3C `traceparent` header) carries the trace across HTTP/gRPC/message-queue hops. A trace that stops at the service boundary is half-blind.
- **Attributes over span names for high-cardinality data** — span name `GET /users/:id` (low cardinality), `user_id` as an attribute (high cardinality). Putting the ID in the name explodes your trace index.
- **Follow OTel [semantic conventions](https://opentelemetry.io/docs/specs/semconv/)** — standardized attribute names (`http.request.method`, `db.system`, `server.address`) so backends understand your spans without custom config.

## Metrics

Two canonical monitoring methods:

- **RED** (request-driven services): **R**ate (requests/sec), **E**rrors (failed requests/sec), **D**uration (latency distribution). Instrument every endpoint with these three.
- **USE** (resources): **U**tilization, **S**aturation, **E**rrors. For thread pools, connection pools, queues, caches.

Practices:

- **Histograms over averages** for latency — an average hides the p99 that's hurting users.
- **Low-cardinality labels** — `endpoint`, `status_class` (2xx/4xx/5xx), `method`. Never `user_id` or `request_id` as a metric label — it explodes the time-series database.
- **Counters for events, gauges for levels, histograms for distributions** — pick the instrument that matches the quantity.

## Correlation IDs

- Accept an inbound request/trace ID; generate one if absent.
- Attach it to every log line, propagate it to every downstream call, and return it to the client (in the response and in error bodies — see `references/api-design.md`).
- This is the thread that ties a user's bug report to the exact server-side trace and logs.

## Health and readiness

- **Liveness** — "is the process up?" (cheap, no dependencies).
- **Readiness** — "can it serve traffic?" (checks dependencies: DB reachable, pool not exhausted). Used by orchestrators to route traffic.
- Keep them separate; a failing dependency should fail readiness (stop traffic) without failing liveness (triggering a restart loop).

## Language SDKs

OTel has stable SDKs per language. Wire the SDK at the application edge (the imperative shell — principle 16), not deep in business logic:

- **Python**: `opentelemetry-sdk` + auto-instrumentation (`opentelemetry-instrument`). Pairs with `structlog` for logs.
- **TypeScript/Node**: `@opentelemetry/sdk-node` + auto-instrumentations. `pino` for structured logs.
- **Rust**: `tracing` + `tracing-opentelemetry` + `opentelemetry` exporter. `tracing` spans become OTel spans.
- **Bash**: no OTel SDK; emit structured (JSON) log lines to stdout/stderr and let the log collector parse them. Include a correlation ID passed via env.

Instrument at the boundary; keep the business core pure (principle: pure/impure separation). The clock, the tracer, and the logger are injected at the edge (principle 16).
