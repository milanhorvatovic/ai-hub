# Persistence — industry conventions

Language-agnostic database and persistence practices. Applies whenever the code under change reads or writes a datastore. Load alongside the relevant language capability when the task touches queries, ORMs, migrations, or connection management.

> **The ORM, pooling and migration tools named below were last checked 2026-08.** The rules do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../SKILL.md`.

## Queries

### N+1 queries

The single most common persistence performance bug. A loop that issues one query per iteration:

```
users = fetch_all_users()          # 1 query
for user in users:
    user.orders = fetch_orders(user.id)   # N queries
```

Fix: batch (one `WHERE user_id IN (...)`), join, or use a dataloader (GraphQL). ORMs offer eager-loading (`select_related` / `prefetch_related` in Django, `joinedload` in SQLAlchemy, `include` in Prisma) — use it when you know you'll traverse the relation.

Detect N+1 in tests by asserting query count, not just result correctness.

### Prepared statements / parameterization

- **Always parameterize.** `WHERE id = ?` with a bound parameter, never string-concatenated SQL (principle 13 — SQL injection).
- ORMs parameterize by default; raw queries are where injection sneaks in.

### Select only what you need

- `SELECT col_a, col_b` over `SELECT *` for hot paths — less I/O, stable under schema changes, and the query documents what it uses.
- Don't load full entities to read one field.

### Indexes

- Index the columns you filter and join on. An unindexed `WHERE` on a large table is a full scan.
- Composite index column order matters: most-selective-first, and match the query's filter order.
- Indexes cost write throughput — don't index every column. Index for the queries you actually run.

## Transactions

- **Keep transactions short.** A transaction held open across a network call or user think-time holds locks and exhausts the connection pool.
- **One unit of work per transaction.** Wrap the operations that must succeed-or-fail together; don't wrap a whole request handler.
- **Choose the isolation level deliberately.** `READ COMMITTED` (default in most DBs) vs `SERIALIZABLE` (correctness at the cost of contention). Know which anomalies (dirty/non-repeatable/phantom reads) the level permits.
- **Handle serialization failures** — under `SERIALIZABLE` / optimistic concurrency, transactions can be aborted and must be retried. The retry is the caller's responsibility.

## Connection management

- **Pool connections.** Opening a connection per request is slow and exhausts DB limits. Use the framework's pool (`SQLAlchemy` engine pool, `pgx` pool, `HikariCP`, Prisma's pool).
- **Size the pool** to the database's `max_connections`, divided across app instances — not "as many as possible."
- **Set statement and connection timeouts** — a runaway query should be killed, not hold a connection forever.
- **Return connections promptly** — use `with` / RAII / `defer` so a connection is released even on error.

## Migrations

- **Migrations are code** — versioned, reviewed, in the repo. Tools: Alembic (Python), Prisma Migrate / Drizzle (TS), `sqlx migrate` / Diesel (Rust), Flyway / Liquibase (JVM).
- **Forward-only in production.** Down-migrations are for local dev; production rolls forward with a new migration.
- **Backward-compatible deploys** — for zero-downtime: expand (add nullable column) → backfill → switch reads → switch writes → contract (drop old column), across multiple deploys. Never add a `NOT NULL` column without a default to a large live table in one step.
- **Test migrations** against a copy of production-shaped data, not an empty schema.
- **Separate schema changes from data changes** when the data change is large — a long-running backfill inside a migration locks the table.

## Data modeling

- **Single source of truth** (principle 18) — don't denormalize derived values without a justification and an invalidation plan.
- **Use the database's types** — `timestamptz` not a string, `numeric` not float for money, native JSON columns over stringified blobs when you query into them.
- **Constraints in the database** — `NOT NULL`, `UNIQUE`, `FOREIGN KEY`, `CHECK`. The DB is the last line of integrity defense; application validation is not enough under concurrency.
- **Soft deletes deliberately** — a `deleted_at` column means every query must filter it; decide whether you actually need it vs a real delete + audit log.

## Caching

- **Cache invalidation is hard** (principle 18) — only cache when measured contention demands it, and implement invalidation alongside.
- **Cache-aside** (read-through on miss, write invalidates) is the common pattern.
- **Set TTLs** — even with explicit invalidation, a TTL bounds the blast radius of a missed invalidation.
- **Cache keys** include the schema version / deploy version so a deploy doesn't serve stale-shaped data.

## Observability of persistence

- Log slow queries (most DBs have a slow-query log; ORMs can log query timing).
- Emit query-count and query-duration metrics per endpoint (see `observability.md`) — N+1 shows up as a query-count spike.
- Trace queries as spans within the request trace so a slow endpoint points at the slow query.
