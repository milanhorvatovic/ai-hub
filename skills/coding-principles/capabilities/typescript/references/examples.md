# TypeScript — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../../references/principles.md`; the language idioms and rules live in `../capability.md`. This file holds only the code.

## Principle 2 — Root cause over bandaid (reproducing test first)

```typescript
// bandaid — `items` is "sometimes undefined", so guard and move on
function totalCents(order: Order): number {
  if (!order.items) return 0;
  return order.items.reduce((sum, i) => sum + i.priceCents, 0);
}
```

```typescript
// the failing test comes first, and it names the real bug: the parser drops
// `items` when the cart is empty, so the shape is wrong before anyone reads it
test("parseOrder keeps an empty items array", () => {
  expect(parseOrder({ id: "o1", items: [] }).items).toEqual([]);
});

// fix where the bad value is produced
function parseOrder(raw: unknown): Order {
  const parsed = OrderSchema.parse(raw);
  return { id: parsed.id, items: parsed.items };
}

// and the guard comes out — `Order["items"]` is `CartItem[]`, so it was unreachable
function totalCents(order: Order): number {
  return order.items.reduce((sum, i) => sum + i.priceCents, 0);
}
```

## Principle 5 — Trust internal code; validate only at boundaries

```typescript
// an internal helper written as if its callers were untrusted
function applyDiscount(cart: Cart, percent: number): Cart {
  if (!cart) throw new Error("cart is required");                    // type says Cart, not Cart | null
  if (typeof percent !== "number") throw new Error("percent must be a number");  // already number
  if (percent < 0 || percent > 100) throw new Error("percent out of range");
  return { ...cart, totalCents: Math.round(cart.totalCents * (1 - percent / 100)) };
}
```

```typescript
// the range check was the only real one, so it moves to the boundary that
// admits the value — where it can reject with a useful message
const DiscountRequest = z.object({ percent: z.number().min(0).max(100) });

app.post("/carts/:id/discount", async (req, res) => {
  const { percent } = DiscountRequest.parse(req.body);
  const cart = await carts.fetch(req.params.id);
  res.json(toPublicCart(applyDiscount(cart, percent)));
});

// internal code trusts its types
function applyDiscount(cart: Cart, percent: number): Cart {
  return { ...cart, totalCents: Math.round(cart.totalCents * (1 - percent / 100)) };
}
```

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

## Mantra — Make illegal states unrepresentable (pairs with strong typing)

```typescript
// three booleans and two optionals: 32 encodable states, most of them nonsense
// — loading and error at once, success with no data, data alongside an error
interface RequestState {
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
  data?: User;
  error?: Error;
}
```

```typescript
// a discriminated union: four states, and the payload exists exactly where it
// means something — no optional chaining, no "this can't happen" branch
type RequestState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: User }
  | { status: "error"; error: Error };

function describe(state: RequestState): string {
  switch (state.status) {
    case "idle":
      return "waiting to start";
    case "loading":
      return "loading…";
    case "success":
      return `loaded ${state.data.name}`;      // data is present here; no `?.`
    case "error":
      return `failed: ${state.error.message}`;
  }
}
```

Note the missing `default`: with `strict` on, that is what makes the switch exhaustive, so adding a fifth state turns every unhandled `switch` into a compile error instead of a silent `undefined`. A `default` branch would throw that away. The compiler is now enforcing the state machine the interface could only describe.

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

## Principle 21 — Comments earn their place

```typescript
// every comment here restates the line under it
// create the payment client
const client = new PaymentClient(config);

// loop over the charges
for (const charge of charges) {
  // retry three times
  await retry(() => client.capture(charge), 3);
}
```

```typescript
const client = new PaymentClient(config);

for (const charge of charges) {
  // Capture is only idempotent from API v3 up and this account is pinned to v2
  // by contract, so there is no retry that is safe here: a connection failure
  // can land after the charge commits, and we cannot tell that case from one
  // that never reached the gateway. Ambiguous failures go to reconciliation.
  // Do not add a retry to this loop without an idempotency key.
  await captureOrQueueForReconciliation(client, charge);
}
```

Three comments became one, and the survivor is the only one that was carrying anything: a constraint the reader cannot see from this file, and the reason the retry predicate is not the default. TSDoc on an exported symbol is judged by the same bar — see the documentation section of `best-practices.md` for when the project's own config settles it instead.
