# Rust — examples by principle

Concrete before/after code anchored to numbered principles from the parent skill. The principle prose lives in `../../../references/principles.md`; the language idioms and rules live in `../capability.md`. This file holds only the code.

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

## Mantra 11 — Make illegal states unrepresentable (pairs with strong typing)

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
