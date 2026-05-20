# TypeScript — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../references/principles.md`; the language idioms and rules live in `capability.md` (sibling). This file holds only the code.

## Principle 16 — Inject time, randomness, and external state

```typescript
// non-deterministic — Date.now() and uuid() called from business logic
function createSession(userId: string): Session {
  return {
    id: crypto.randomUUID(),
    userId,
    createdAt: Date.now(),
    expiresAt: Date.now() + SESSION_TTL_MS,
  };
}
```

```typescript
// inject clock and id generator; wiring lives at the entry point
interface Deps { now: () => number; uuid: () => string }

function createSession(userId: string, deps: Deps): Session {
  const createdAt = deps.now();
  return {
    id: deps.uuid(),
    userId,
    createdAt,
    expiresAt: createdAt + SESSION_TTL_MS,
  };
}

// main.ts (the shell):
const session = createSession(userId, { now: Date.now, uuid: crypto.randomUUID });

// test — deterministic, no time-freezing patches
const session = createSession("u1", { now: () => 1000, uuid: () => "fixed-id" });
```

## Principle 18 — Single source of truth for state

```typescript
// two sources of truth — items and total can drift
interface Cart {
  items: CartItem[];
  total: number;          // duplicates sum(items) — invalidation hazard
  itemCount: number;      // duplicates items.length — same
  isEmpty: boolean;       // duplicates items.length === 0 — same
}
```

```typescript
// one source; the rest are derived
interface Cart {
  items: CartItem[];
}

const cartTotal = (cart: Cart) => cart.items.reduce((s, i) => s + i.price * i.qty, 0);
const cartItemCount = (cart: Cart) => cart.items.length;
const cartIsEmpty = (cart: Cart) => cart.items.length === 0;
```

## Principle 19 — Boundaries serialize output

```typescript
// ships the entire internal object — next field you add (password_hash,
// internal_id, audit_trail) silently leaks to the client
res.json(user);
```

```typescript
// explicit serializer; reviewers see exactly what crosses the boundary
function toPublicUser(u: User): PublicUser {
  return { id: u.id, name: u.name, email: u.email };
}
res.json(toPublicUser(user));
```
