# Rust — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../../references/principles.md`; the language idioms and rules live in `../capability.md`. This file holds only the code.

## Principle 2 — Root cause over bandaid (reproducing test first)

```rust
// bandaid — clamps the symptom; the real bug (negative quantity upstream)
// survives and corrupts every downstream total
pub fn line_total(qty: i64, unit_cents: i64) -> i64 {
    (qty * unit_cents).max(0)
}
```

```rust
// reproducing test first — fails before the fix, pins the root cause after
#[test]
fn rejects_negative_quantity() {
    let err = OrderLine::new(-3, 250).unwrap_err();
    assert_eq!(err, OrderError::NegativeQuantity { qty: -3 });
}

// fix at the boundary where the bad state enters
impl OrderLine {
    pub fn new(qty: i64, unit_cents: i64) -> Result<Self, OrderError> {
        if qty < 0 {
            return Err(OrderError::NegativeQuantity { qty });
        }
        Ok(Self { qty, unit_cents })
    }
}
```

Validating in the constructor pairs with principle 5: downstream code receives an `OrderLine` that cannot hold a negative quantity and trusts it.

## Principle 5 — Trust internal code; validate at boundaries

```rust
// defensive — Option::unwrap is the spelling; explicit if-let-else duplicates
// what the type system already forced the caller to handle
fn user_label(user: Option<&User>) -> String {
    if user.is_none() {
        return "(none)".to_string();
    }
    let u = user.unwrap();
    if u.name.is_empty() {
        return "(unnamed)".to_string();
    }
    u.name.clone()
}
```

```rust
// trust the types; let pattern matching do the work
fn user_label(user: Option<&User>) -> String {
    match user {
        None => "(none)".into(),
        Some(u) if u.name.is_empty() => "(unnamed)".into(),
        Some(u) => u.name.clone(),
    }
}
```

For fallible operations, propagate with `?` instead of `unwrap()` / `expect()` in non-test code.

## Mantra — Make illegal states unrepresentable (pairs with strong typing)

```rust
// bag of optionals — many incoherent combinations compile
struct LoadState<T> {
    loading: bool,
    data: Option<T>,
    error: Option<String>,
}
// { loading: true, data: Some(_), error: Some(_) } compiles but is nonsense
```

```rust
// sum type — only the four valid states exist
enum LoadState<T> {
    Idle,
    Loading,
    Success(T),
    Error(String),
}
// nonsense states do not type-check
```

## Principle 15 — Mock at boundaries, not at internal logic

```rust
// fakes the dependency *inside* the production path — test-only branches in
// business logic, and the test still cannot observe what was reserved
pub fn process_order(order: &Order) -> Result<Receipt, OrderError> {
    #[cfg(test)]
    let reserved = true;
    #[cfg(not(test))]
    let reserved = warehouse::reserve(&order.sku, order.qty)?;
    // ...
}
```

```rust
// the boundary is a trait the production code already depends on; the test
// double implements it and records observable behavior
pub trait Inventory {
    fn reserve(&self, sku: &Sku, qty: u32) -> Result<(), StockError>;
}

pub fn process_order(order: &Order, inventory: &dyn Inventory) -> Result<Receipt, OrderError> {
    // ...
}

#[cfg(test)]
mod tests {
    struct FakeInventory {
        stock: HashMap<Sku, u32>,
        reservations: RefCell<Vec<(Sku, u32)>>,
    }

    impl Inventory for FakeInventory {
        fn reserve(&self, sku: &Sku, qty: u32) -> Result<(), StockError> {
            // check self.stock, push into self.reservations
        }
    }

    #[test]
    fn checkout_reserves_stock_when_items_available() {
        let inventory = FakeInventory::with_stock([("sku-1", 10)]);
        let receipt = process_order(&order("sku-1", 2), &inventory).unwrap();
        assert_eq!(inventory.reservations(), vec![(sku("sku-1"), 2)]);
        assert_eq!(receipt.status, Status::Confirmed);
    }
}
```

The second test survives any internal refactor of `process_order` because the double lives at the trait boundary and the assertions read observable behavior only — no mocking framework needed.

## Principle 16 — Inject time, randomness, and external state

```rust
// non-deterministic — chrono::Utc::now() called inside business logic
pub fn create_session(user_id: UserId) -> Session {
    Session {
        id: uuid::Uuid::new_v4(),
        user_id,
        created_at: chrono::Utc::now(),
        expires_at: chrono::Utc::now() + chrono::Duration::hours(1),
    }
}
```

```rust
// inject via a trait so tests can substitute a fake clock and id source
pub trait Clock {
    fn now(&self) -> chrono::DateTime<chrono::Utc>;
}

pub trait IdSource {
    fn new_id(&self) -> uuid::Uuid;
}

pub fn create_session(user_id: UserId, clock: &dyn Clock, ids: &dyn IdSource) -> Session {
    let created_at = clock.now();
    Session {
        id: ids.new_id(),
        user_id,
        created_at,
        expires_at: created_at + chrono::Duration::hours(1),
    }
}
```

For lighter cases, take closures or function pointers (`now: impl Fn() -> Instant`) instead of trait objects.

## Principle 19 — Boundaries parse input

```rust
// serde::Value as a stand-in for "we'll figure it out later" — downstream
// code receives untyped JSON and pays the validation cost on every read
pub fn handle_order(body: serde_json::Value) -> Result<Receipt, Error> {
    let user_id = body["user_id"].as_str().ok_or(Error::BadInput)?;
    let items = body["items"].as_array().ok_or(Error::BadInput)?;
    // ...
}
```

```rust
// parse at the edge into a typed struct; downstream code receives OrderRequest
#[derive(serde::Deserialize)]
pub struct OrderRequest {
    user_id: UserId,
    items: Vec<OrderItem>,
}

pub fn handle_order(req: OrderRequest) -> Result<Receipt, Error> {
    process(req.user_id, &req.items)   // fully typed past this line
}
```
