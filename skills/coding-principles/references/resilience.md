# Resilience — industry conventions

Language-agnostic fault-tolerance patterns for code that calls across a network or process boundary. Load when the code under change makes outbound calls (HTTP, RPC, DB, cache, queue) or coordinates distributed work. The canon here is the *Release It!* (Nygard) family of stability patterns.

Scope boundary: this is resilience *as code* — how a service survives its dependencies failing. Deployment-level resilience (multi-region, autoscaling, failover infrastructure) is ops/SRE, not here.

The core assumption: **every remote call will eventually fail, hang, or slow down.** Code that assumes the network is reliable is broken; it just hasn't failed yet.

## Timeouts and deadlines

- **Every outbound call has a timeout.** An un-timed call inherits the OS default (often minutes) and holds a thread/connection the whole time — one slow dependency exhausts the pool and takes down the whole service.
- **Deadlines propagate.** If the inbound request has 2s left, downstream calls get *less* than 2s, not a fresh 2s. gRPC propagates deadlines natively; with HTTP, pass a remaining-budget header or compute it.
- **Timeout < the caller's timeout.** A 30s DB query timeout behind a 10s request timeout is pointless — the client already gave up.

## Retries

- **Only retry idempotent / safe operations.** Retrying a non-idempotent `POST` double-charges. Use idempotency keys (see `api-design.md`) to make retries safe.
- **Only retry transient failures** — timeouts, `503`, `429`, connection resets. Never retry `400`/`401`/`403`/`422` (the request is wrong; retrying it unchanged just wastes calls).
- **Exponential backoff + jitter.** `delay = base * 2^attempt`, then add randomness. Without jitter, all clients retry in lockstep and create a thundering herd that re-downs the recovering dependency. Full jitter (`random(0, base * 2^attempt)`) is the AWS-recommended default.
- **Bounded.** Cap attempts (e.g. 3) and total time. Infinite retries turn a blip into an outage.
- **Retry budgets** — cap retries as a fraction of total traffic (e.g. ≤10%). When a dependency is down, retries amplify load exactly when it can least handle it; a budget prevents the amplification.

## Circuit breakers

When a dependency is failing, stop calling it for a while — fail fast instead of piling up timeouts.

- **States**: closed (calls pass), open (calls fail immediately), half-open (a probe call tests recovery).
- Trip open after an error-rate or consecutive-failure threshold; after a cooldown, allow a probe; close on success.
- Pairs with a fallback (below) — when the breaker is open, serve degraded results, don't just error.
- Libraries: `resilience4j` (JVM), `polly` (.NET), `tenacity`/`pybreaker` (Python), `cockatiel`/`opossum` (Node), `failsafe`/`tower` middleware (Rust).

## Bulkheads

Isolate resources so one failing dependency can't starve the others. Separate connection pools / thread pools / semaphores per downstream — if dependency A hangs, calls to B still have capacity. (Named after ship compartments: a breach floods one, not all.)

## Graceful degradation and fallbacks

- When a non-critical dependency is down, degrade rather than fail the whole request: serve a cached/stale value, a default, or omit the optional section.
- Distinguish **critical** (can't serve without it — fail the request) from **optional** (nice-to-have — degrade). Make this explicit in the code; don't let a recommendations-service outage take down checkout.

## Idempotency and exactly-once

- True exactly-once delivery doesn't exist over a network. Design for **at-least-once + idempotent processing**: dedupe by idempotency key / message ID so reprocessing is harmless.
- Persist the processed-key set (with a TTL) so retries and redeliveries are no-ops.

## Queues and async work

- **Dead-letter queue (DLQ)** for messages that fail repeatedly — don't let one poison message block the queue or retry forever. Alert on DLQ depth.
- **Visibility timeout / ack discipline** — ack only after successful processing so a crash mid-process redelivers, not drops.
- **Backpressure** — when downstream can't keep up, slow intake (bounded queues, rate limiting) rather than buffering unboundedly until OOM.

## Health checks

- **Liveness** (process up) vs **readiness** (can serve — dependencies reachable). See `observability.md`. A dependency outage should fail readiness (shed traffic) without failing liveness (restart loop).

## Principle alignment

- Resilience logic lives at the **boundary** (the imperative shell — pure/impure separation): the retry wrapper, circuit breaker, and timeout wrap the outbound call; the pure business core stays unaware.
- **Fail fast, fail loud** (mantra): a circuit breaker *is* fail-fast — it surfaces the dependency failure immediately instead of hanging.
- **YAGNI check**: don't wrap every internal function call in retries + breakers. These patterns are for *crossing a trust/network boundary*; in-process calls don't need them. A single-process CLI needs none of this.
- **Observability**: instrument retries (count, exhaustion), breaker state changes, and timeouts as metrics — a silent retry storm is invisible until it's an outage.
