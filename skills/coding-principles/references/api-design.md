# API design — industry conventions

Language-agnostic conventions for designing service APIs (REST, GraphQL, gRPC). Applies whenever the code under change exposes or consumes a network API. Load alongside the relevant language capability when the task touches HTTP handlers, RPC services, or client code.

These are *industry* conventions, not this skill's invention — cite them when an API choice needs justification.

## REST / HTTP

### Status codes

Use the status code that matches the semantics; don't return `200` with an `{error: ...}` body.

| Code | When                                                              |
| ---- | --------------------------------------------------------------- |
| 200  | Success with a body                                             |
| 201  | Resource created (return `Location` header + the created entity) |
| 202  | Accepted for async processing (not yet done)                   |
| 204  | Success, no body (e.g. DELETE)                                  |
| 400  | Malformed request (client should not retry unchanged)          |
| 401  | Not authenticated                                              |
| 403  | Authenticated but not authorized                               |
| 404  | Resource not found (or hidden for authz reasons)               |
| 409  | Conflict (version mismatch, duplicate)                         |
| 422  | Well-formed but semantically invalid                           |
| 429  | Rate limited (include `Retry-After`)                           |
| 500  | Server bug (never leak detail to the client — see principle 13) |
| 503  | Temporarily unavailable (include `Retry-After`)                |

### Idempotency

- `GET`, `PUT`, `DELETE` must be idempotent — same request repeated yields the same state.
- `POST` is not idempotent by default. For payment-like operations, accept an **idempotency key** header so retries don't double-charge.
- Make retries safe: a client that times out and retries should not corrupt state.

### Pagination

- Cursor-based (`?cursor=...&limit=...`) for large or mutating datasets — stable under inserts/deletes.
- Offset-based (`?offset=...&limit=...`) only for small, static datasets — it skips/duplicates rows when the data changes mid-pagination.
- Always cap `limit` server-side; never let a client request unbounded results.
- Return pagination metadata (next cursor, total if cheap to compute).

### Versioning

- Version from day one. URL path (`/v1/...`) is the most visible and cache-friendly; header-based (`Accept: application/vnd.api+json;version=1`) is purer but harder to debug.
- Additive changes (new optional fields, new endpoints) don't need a version bump. Breaking changes (removed/renamed fields, changed types, changed semantics) do.
- Never break v1 while v1 clients exist.

### Error responses

- Consistent shape across the whole API: `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`.
- `code` is a stable machine-readable string (`INVALID_EMAIL`), not a localized message.
- `message` is human-readable but does not leak internals (no stack traces, SQL, file paths — principle 13).
- Include a `request_id` clients can quote in support tickets (correlates with server logs — see `references/observability.md`).

### General

- Nouns for resources (`/users/123/orders`), verbs only for actions that don't map to CRUD (`/orders/123/cancel`).
- Plural collection names (`/users`, not `/user`).
- Use HTTP caching headers (`ETag`, `Cache-Control`) for read-heavy endpoints.
- Document with OpenAPI/Swagger; generate clients from the spec rather than hand-writing.

## GraphQL

- **Schema-first**: the schema is the contract; resolvers implement it. Nullability is part of the type — be deliberate (`String!` vs `String`).
- **N+1 is the default failure mode** — use DataLoader (batching + caching) for every relation resolver. See `references/persistence.md`.
- **Pagination**: Relay connection spec (`edges`/`node`/`pageInfo`/`cursor`) is the industry standard.
- **Errors**: partial results + a top-level `errors` array; use error extensions for machine-readable codes.
- **Depth/complexity limiting**: cap query depth and cost server-side — unbounded nested queries are a DoS vector.

## gRPC

- **Proto is the contract.** Field numbers are forever — never reuse a removed field's number; mark removed fields `reserved`.
- **Backward compatibility**: adding fields is safe; changing types or field numbers is not.
- **Streaming** for large or long-lived data; unary for request/response.
- **Status codes**: use the canonical gRPC codes (`INVALID_ARGUMENT`, `NOT_FOUND`, `ALREADY_EXISTS`, `PERMISSION_DENIED`, `UNAVAILABLE`, etc.), not custom ints.
- **Deadlines**: clients set deadlines; servers respect them and propagate to downstream calls.

## Cross-cutting (any API style)

- **Validate at the boundary** (principle 19) — parse the request into a typed value; reject malformed input with a useful error.
- **Authorize every request** (principle 13) — authentication ≠ authorization.
- **Rate-limit** public endpoints; return `429` + `Retry-After`.
- **Timeouts everywhere** — every outbound call from a handler has a deadline; never make an un-timed network call in a request path.
- **Correlation IDs** — accept an inbound trace/request ID, generate one if absent, propagate it to every downstream call and every log line (see `references/observability.md`).
