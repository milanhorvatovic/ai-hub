# Data-handling footguns — industry conventions

Language-agnostic correctness practices for the three classic "works in dev, corrupts in prod" data categories: dates/times, numbers/money, and text/encoding. Load when the code under change handles timestamps, currency or precise arithmetic, or text from any external source.

These are the most common cross-language correctness bugs. None of them are exotic; all of them ship to production constantly.

## Dates and times

The rule: **store and compute in UTC; convert to local only at display.**

- **Store UTC.** Persist timestamps as UTC (`timestamptz` in Postgres, epoch millis, or ISO 8601 with offset). Never store a local time without its zone — it's ambiguous twice a year (DST fall-back) and meaningless elsewhere.
- **Timezone-aware types only.** Never use naive datetimes in business logic. Python: `datetime` with `tzinfo` (or `whenever`/`pendulum`); never `datetime.now()` (use `datetime.now(timezone.utc)`). JS: `Temporal` (or `date-fns-tz` / `Luxon`); the legacy `Date` is local-zone-flavored and error-prone. Rust: `chrono::DateTime<Utc>` / `time::OffsetDateTime`.
- **ISO 8601 / RFC 3339 on the wire.** `2026-05-19T14:30:00Z`. Unambiguous, sortable, parseable everywhere. Never serialize locale-formatted dates between systems.
- **Wall clock vs monotonic clock.** For *timestamps* (when did this happen) use the wall clock. For *durations / timeouts / elapsed time* use a monotonic clock (`time.monotonic()`, `performance.now()`, `Instant::now()`) — the wall clock can jump backward (NTP sync, DST) and produce negative durations.
- **DST and arithmetic.** "Add 1 day" ≠ "add 24 hours" across a DST boundary. Use a calendar-aware library for calendar arithmetic; use plain duration math only for elapsed time. Some days have 23 or 25 hours; some minutes have 61 seconds (leap seconds).
- **Date-only vs datetime.** A birthday is a date, not an instant — don't attach a time/zone to it and shift it across midnight. Use a date type, not a datetime-at-midnight.
- **Inject the clock** (principle 16) — `now` is an input, not a global call. Makes time-dependent logic testable.

## Numbers and money

The rule: **never use binary floating point for money or exact decimal values.**

- **Money** — use integer minor units (cents) or a decimal type (`decimal.Decimal`, `BigDecimal`, `rust_decimal`, JS `decimal.js` / integer cents). `0.1 + 0.2 != 0.3` in float; charging customers with float rounds wrong and fails audits.
- **Rounding** — be explicit about the mode (half-even/banker's vs half-up) and the scale. Financial code usually wants banker's rounding to avoid bias. Don't rely on the default `round()` (Python's is banker's; JS's is half-up — they differ).
- **Integer overflow** — know your width. Rust panics in debug / wraps in release (use checked/saturating/wrapping ops deliberately). C-family wraps silently. Python ints are arbitrary-precision (no overflow) but DB columns aren't — a value that fits in Python overflows `INT4`.
- **Float comparison** — never `==` on floats from computation; compare with a tolerance (`abs(a-b) < epsilon`) when float is genuinely appropriate (physics, ML — not money).
- **`NaN` / `Infinity`** — `NaN != NaN`; propagates silently through arithmetic; serializes badly (not valid JSON). Guard at boundaries; reject or handle explicitly.
- **Currency is not just a number** — an amount without a currency code is a bug waiting to happen. Model `Money { amount, currency }`; never add two amounts of different currencies (make illegal states unrepresentable — mantra).

## Text and encoding

The rule: **UTF-8 everywhere; decode bytes to text at the boundary, encode text to bytes at the boundary; in between, work with text.**

- **UTF-8 by default.** Declare it explicitly when reading/writing files, sockets, subprocess output. Don't rely on the platform default encoding (Windows is often not UTF-8; `locale`-dependent defaults cause "works on my machine").
- **Bytes vs string are different types.** Decode at input (`bytes -> str`), encode at output (`str -> bytes`). Mixing them is the source of `UnicodeDecodeError` / mojibake. Python and Rust enforce the distinction in the type system; lean on it. JS strings are UTF-16 internally — be careful with byte lengths.
- **Length is ambiguous.** "Length" can mean bytes, UTF-16 code units, Unicode code points, or grapheme clusters (what a human calls a character). An emoji is 1 grapheme, multiple code points, multiple bytes. For "max 100 characters" validation, decide which you mean; for display truncation, use graphemes (don't split a multi-byte char).
- **Normalization.** The same visible string can have multiple byte representations (`é` as one code point vs `e` + combining accent). Normalize (NFC for storage/comparison usually) before comparing or deduplicating user input — otherwise two "identical" usernames don't match.
- **Don't index into strings by byte offset** in variable-width encodings — you'll split a character. Use the language's grapheme/char-aware APIs.
- **Sanitize at the boundary** (principle 19 / security) — text from users can contain control characters, bidi overrides (Trojan Source attacks), null bytes. Validate and normalize on the way in.

## Principle alignment

- All three categories are **boundary** problems (principle 19): parse the wire format / decode bytes / validate the number *at the edge* into a correct typed value (`DateTime<Utc>`, `Money`, `str`), then trust it inward (principle 5).
- **Make illegal states unrepresentable** (mantra): a naive datetime, a bare float for money, or a `bytes` where text is meant are all "illegal states" a good type makes impossible. Model `Money`, require `tzinfo`, keep `bytes`/`str` distinct.
- **Inject the clock** (principle 16) for testable time logic.
- **Strong typing** (mantra): use the date/decimal/text types the language provides instead of raw `int`/`float`/`str` — the type carries the invariant.

## Per-language pointers

- **Python**: `datetime` (tz-aware) / `whenever` / `pendulum`; `decimal.Decimal`; explicit `encoding="utf-8"` on `open`; `unicodedata.normalize`.
- **TypeScript/Node**: `Temporal` (or Luxon); integer cents or `decimal.js`; `Buffer`/`TextDecoder` with explicit encoding; `String.prototype.normalize()`; `Intl.Segmenter` for graphemes.
- **Rust**: `chrono` / `time`; `rust_decimal`; `&str` is guaranteed UTF-8; `unicode-segmentation` for graphemes; `unicode-normalization`.
- **Bash**: avoid date/number/encoding-sensitive logic — `date` differs GNU vs BSD (see `references/platform-matrix.md`), no decimal type (`bc`/`awk` for math), locale affects sorting/formatting. Past trivial cases, this is a "leave bash" signal.
