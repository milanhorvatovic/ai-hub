# Python — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../references/principles.md`; the language idioms and rules live in `capability.md` (sibling). This file holds only the code.

## Principle 4 — No *speculative* generality

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

When SMS arrives later, *that* is when you extract the seam — and you do it knowing what both implementations actually look like.

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

Validation belongs at the *entry* of the module/service — the handler that received the request, the parser that read the file.

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
