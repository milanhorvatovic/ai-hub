# Python — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../../references/principles.md`; the language idioms and rules live in `../capability.md`. This file holds only the code.

## Principle 2 — Root cause over bandaid (reproducing test first)

```python
# bandaid — a KeyError showed up in production, so swallow it and default
def user_timezone(profile: dict) -> str:
    try:
        return profile["settings"]["timezone"]
    except KeyError:
        return "UTC"
```

```python
# the failing test comes first, and it names the real bug: rows written before
# the settings migration load with `settings` absent
def test_load_profile_fills_settings_for_pre_migration_rows():
    profile = load_profile(row_without_settings)
    assert profile["settings"]["timezone"] == "UTC"

# fix where the bad shape is produced
def load_profile(row: Row) -> dict:
    return {"id": row.id, "settings": row.settings or DEFAULT_SETTINGS}

# and the except comes out — every profile now has settings, so catching
# KeyError here would only hide the next bug that breaks that invariant
def user_timezone(profile: dict) -> str:
    return profile["settings"]["timezone"]
```

## Principle 4 — No _speculative_ generality

Adding a notification feature with one channel today (email).

```python
# speculative — one impl behind a strategy interface "for future channels"
class NotificationChannel(ABC):
    @abstractmethod
    def send(self, user: User, msg: str) -> None: ...

class EmailChannel(NotificationChannel):
    def send(self, user: User, msg: str) -> None:
        smtp.send(user.email, msg)

def notify(user: User, msg: str, channel: NotificationChannel) -> None:
    channel.send(user, msg)
```

```python
# earned — one impl, named for what it does; extract the seam when SMS lands
def send_email(user: User, msg: str) -> None:
    smtp.send(user.email, msg)
```

When SMS arrives later, _that_ is when you extract the seam — and you do it knowing what both implementations actually look like.

## Principle 5 — Trust internal code; validate only at boundaries

A function called only from within the module, after the caller has already validated:

```python
# defensive — impossible states the type system already excludes
def calculate_total(items: list[Item]) -> Decimal:
    if items is None:
        return Decimal(0)
    if not isinstance(items, list):
        raise TypeError("expected list")
    if any(item is None for item in items):
        items = [i for i in items if i is not None]
    return sum(item.price for item in items)
```

```python
# trusting — lets the type system do its job
def calculate_total(items: list[Item]) -> Decimal:
    return sum((item.price for item in items), Decimal(0))
```

Validation belongs at the _entry_ of the module/service — the handler that received the request, the parser that read the file.

## Principle 8 — No half-implementations

```python
# half-impl — looks done, type-checks, lint passes; the refund path is a
# stub that detonates only when fulfillment fails (i.e. when it matters most)
def process_order(order: Order) -> Receipt:
    charged = charge_card(order)
    try:
        fulfillment = create_shipment(order)
    except FulfillmentError as exc:
        refund(charged)              # raise NotImplementedError("coming soon")
        raise OrderFailed(exc) from exc
    return Receipt(charged, fulfillment)
```

```python
# ship all three: charge / fulfill / refund-on-failure. If the refund path
# is not ready, do not ship process_order yet — ship a narrower function
# (charge-then-fulfill, no auto-refund) and document the manual rollback
# procedure as the temporary contract until refund() exists.
def process_order(order: Order, refunder: Refunder) -> Receipt:
    charged = charge_card(order)
    try:
        fulfillment = create_shipment(order)
    except FulfillmentError as exc:
        refunder.refund(charged)
        raise OrderFailed(exc) from exc
    return Receipt(charged, fulfillment)
```

The half-impl is worse than not shipping the feature: callers depend on the function's claimed contract; the stubbed path violates that contract at the worst moment.

## Principle 13 — Security hygiene (no secrets in logs / errors)

```python
# leaks tokens to disk-resident logs
logger.info(f"authenticated request: {request.headers}")
logger.debug(f"calling upstream with {payload}")  # payload contains api_key
```

```python
# redact known sensitive fields; log identifiers and shapes only
logger.info(
    "authenticated request",
    extra={"user_id": user.id, "route": request.path, "method": request.method},
)
logger.debug(
    "calling upstream",
    extra={"endpoint": endpoint, "payload_size": len(payload)},
)
```

```python
# error response leaks the SQL query and stack trace
return JSONResponse(
    status_code=500,
    content={"error": str(exc), "trace": traceback.format_exc()},
)
```

```python
# user gets a generic error; detail goes to internal logs
logger.exception("query failed", extra={"user_id": user.id, "operation": "fetch_orders"})
return JSONResponse(
    status_code=500,
    content={"error": "internal error", "request_id": ctx.request_id},
)
```

## Principle 15 — Mock at boundaries, not at internal logic

```python
# mocks an internal helper; breaks the moment process_order is refactored,
# proves nothing about behavior
def test_checkout_calls_inventory():
    with patch("checkout._reserve_stock") as m:
        process_order(order)
    m.assert_called_once()
```

```python
# mocks the inventory client (a real boundary); asserts on observable behavior
def test_checkout_reserves_stock_when_items_available():
    inventory = FakeInventoryClient(stock={"sku-1": 10})
    receipt = process_order(order, inventory=inventory)
    assert inventory.reservations == [("sku-1", 2)]
    assert receipt.status == "confirmed"
```

The second test survives any internal refactor of `process_order` because it only knows about the public contract (input → output, side effects at the boundary).

## Principle 16 — Inject time, randomness, and external state

```python
# reaches for the clock, the RNG, and the environment from business logic
def issue_token(user_id: str) -> Token:
    return Token(
        value=secrets.token_urlsafe(32),
        user_id=user_id,
        issued_at=datetime.now(tz=timezone.utc),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=int(os.environ["TOKEN_TTL"])),
    )
```

```python
# all three arrive as arguments; note the two `datetime.now()` calls collapsed
# into one, so the token's lifetime is exactly the ttl instead of the ttl plus
# however long the two clock reads were apart
@dataclass(frozen=True)
class TokenPolicy:
    ttl: timedelta

def issue_token(
    user_id: str, now: datetime, new_secret: Callable[[], str], policy: TokenPolicy
) -> Token:
    return Token(
        value=new_secret(),
        user_id=user_id,
        issued_at=now,
        expires_at=now + policy.ttl,
    )

# main.py — the shell reads the environment once and wires the real ones in
policy = TokenPolicy(ttl=timedelta(seconds=int(os.environ["TOKEN_TTL"])))
token = issue_token(user_id, datetime.now(tz=timezone.utc), lambda: secrets.token_urlsafe(32), policy)

# the test needs no freezegun, no monkeypatch, no environment
token = issue_token(
    "u1", datetime(2026, 1, 1, tzinfo=timezone.utc), lambda: "fixed", TokenPolicy(ttl=timedelta(hours=1))
)
assert token.expires_at == datetime(2026, 1, 1, 1, tzinfo=timezone.utc)
```

## Principle 17 — Naming discipline

```python
# misleading or noisy names
def calc(u, lst):           # what is u? what is lst?
    cnt = 0
    for x in lst:
        if x.adm:           # adm = admin? administrative? adam?
            cnt += 1
    return cnt

old_user = get_user(uid)    # "old" relative to what? lingers forever
data_v2 = transform(data)   # decay suffix; rot magnet
```

```python
# names carry their meaning
def count_admins(viewer: User, users: list[User]) -> int:
    return sum(1 for u in users if u.is_admin)

current_user = get_user(user_id)
normalized = normalize(raw)
```

## Principle 19 — Boundaries parse input (inbound)

```python
# trusts the wire format blindly; downstream code receives `dict` and guesses
@app.post("/order")
def create_order(payload: dict):
    user_id = payload["user_id"]            # KeyError on bad input
    items = payload.get("items", [])         # silently empty on malformed
    return process(user_id, items)
```

```python
# parse at the edge into a typed value; downstream code receives `OrderRequest`
class OrderRequest(BaseModel):
    user_id: UserId
    items: list[OrderItem]

@app.post("/order")
def create_order(req: OrderRequest):
    return process(req.user_id, req.items)  # fully typed past this line
```

## Principle 21 — Comments earn their place

```python
# a docstring that restates the signature, and comments narrating each line
def normalize_email(email: str) -> str:
    """Normalize an email.

    Args:
        email: The email to normalize.

    Returns:
        The normalized email.
    """
    # lowercase and strip
    email = email.strip().lower()
    # split on the @
    local, _, domain = email.partition("@")
    # handle gmail
    if domain == "gmail.com":
        local = local.replace(".", "")
    return f"{local}@{domain}"
```

```python
def normalize_email(email: str) -> str:
    """Fold an address into the form used to flag likely duplicate signups.

    The transform is lossy and one-way: two addresses that reach different
    inboxes can fold together, so this is a matching hint and nothing more.
    Never use it as an account key, a login identity, or a reply-to — a
    collision there merges two people's accounts.
    """
    email = email.strip().lower()
    local, _, domain = email.partition("@")
    if domain == "gmail.com":
        # Gmail ignores dots in the local part, so `a.b@` and `ab@` reach one
        # mailbox — folding them is what makes two spellings comparable.
        local = local.replace(".", "")
    return f"{local}@{domain}"
```

The rewritten docstring says something the signature cannot — that the return value is lossy, and what that rules out downstream — and the surviving comment explains a line whose behavior would otherwise read as a bug. Note that naming the constraint is what exposes the design question: once the docstring has to say "two inboxes can fold together", using the result as an account key stops looking reasonable, which is the kind of thing a comment earns its place by making visible. Which projects require docstrings at all is settled by their own config; `best-practices.md` covers the Python side of that, and the cross-language rubric lives in the comments capability.
