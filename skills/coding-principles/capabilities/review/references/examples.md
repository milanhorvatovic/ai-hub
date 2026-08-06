# Review — a worked review

One diff carried end to end through the workflow in `../capability.md`, so the output format has a filled-in instance and not only a template. The rules live in that file and in `best-practices.md`; this file shows what following them produces, and — in the closing section — which findings were deliberately not written down.

Python here is incidental. The lens is language-agnostic: the same triage, anchors, and phrasing apply to a Rust or shell diff, and only the per-language reference you reach for while judging changes.

## What the reviewer was given

The diff below, plus the pull-request description: "Fixes double-writes to the refund audit log."

That sentence is part of the input. A change that presents itself as a bug fix is judged against principle 2, and the diff either carries the test that failed before it or it does not.

```diff
--- a/billing/refunds.py
+++ b/billing/refunds.py
@@ -12,6 +12,18 @@ from billing.audit import RefundAudit
-def refund(order_id: OrderId, amount_cents: int) -> Refund:
-    order = orders.fetch(order_id)            # raises OrderNotFound
-    return gateway.refund(order.payment_id, amount_cents)
+def refund(order_id: OrderId, amount_cents: int, reason: str) -> Refund:
+    if amount_cents is None:
+        raise ValueError("amount_cents is required")
+
+    order = orders.fetch(order_id)            # raises OrderNotFound
+    log.info(
+        "refunding order=%s card=%s reason=%s",
+        order_id, order.card_number, reason,
+    )
+
+    # call the gateway, then write the audit row
+    result = gateway.refund(order.payment_id, amount_cents)
+    audit.write(RefundAudit(refund_id=result.id, at=datetime.now(tz=UTC), actor=reason))
+    return result
```

## The review

````markdown
## Summary

Two blockers: a card number reaches the logs, and the bug this fixes has no test. The rest is small.

## Must fix (2)

- [billing/refunds.py:19] **principle 13** — `order.card_number` is interpolated into the `log.info` call, so a full PAN lands in whatever the log ships to. Log the shape instead of the value: `card_last4=%s` with `order.card_last4`, or drop the field — `order_id` is already enough to find the payment.
- [billing/refunds.py] **principle 2** — the description says this fixes double-writes to the audit log, but nothing in the diff fails without the change, so there is no evidence the double-write is actually gone. Add a test that writes two refunds for one order and asserts a single audit row, confirm it fails on `main`, then land it with this fix.

## Should fix (2)

- [billing/refunds.py:14] **principle 5** — `amount_cents` is annotated `int`, so the `is None` branch is unreachable from any caller that typechecks; the guard reads as if callers were untrusted and hides the fact that this function is internal. Delete it. If a `None` genuinely arrives from an HTTP handler upstream, the check belongs in that handler's request parsing, not here.
- [billing/refunds.py:25] **principle 16** — `datetime.now(tz=UTC)` is called inside `refund`, so any test asserting on the audit row's timestamp has to patch the clock. Take the timestamp as a parameter and let the caller pass it:

  ```python
  def refund(order_id: OrderId, amount_cents: int, reason: str, now: datetime) -> Refund:
  ```

## Could fix (1, optional)

- [billing/refunds.py:23] **principle 21** — `# call the gateway, then write the audit row` names what the next two lines already say. Delete it, or replace it with the reason the audit write is not inside a transaction with the gateway call, if there is one.

## Observations

`actor=reason` reads oddly — `reason` is why the refund happened, and an audit row's actor is usually who caused it. If the audit schema really wants the reason there, the field name is the thing to change; if it wants a user, this is a bug I could not confirm from the diff alone. Not a finding, a question for the author.
````

## Why the review looks like this

- **Two musts lead, and the summary says so in one line.** Triage is the shape of the output, not a note inside it. A reader who stops after the summary still knows the change is blocked and why.
- **The principle 2 finding has no line number.** It is about something absent from the diff, so `[billing/refunds.py]` alone is the honest anchor. Inventing a line to satisfy the format would point at code that is not the problem.
- **Each finding names the observable thing first** — `order.card_number` reaching the logs, the unreachable `is None` branch — and the principle number second. A reviewer who has never read this skill can still act on all five.
- **One could, not four.** The diff also uses `result` where the file's other functions use `res`, and the `log.info` call is wrapped in a way `ruff format` would rewrite. Both were dropped: the first matches nothing worth a round trip (principle 9 — the file's local convention wins), and the second is the formatter's job. Stacking those under the card-number finding would cost it attention it needs.
- **The last item is not a finding.** The reviewer could not tell from the diff whether `actor=reason` is a real bug, and a concern without a confident anchor goes to Observations as a question rather than into a severity bucket as a verdict. Inventing an anchor to promote it would be the anti-pattern the capability names.
