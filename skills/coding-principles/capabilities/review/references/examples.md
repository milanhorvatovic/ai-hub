# Review — a worked review

One diff carried end to end through the workflow in `../capability.md`, so the output format has a filled-in instance and not only a template. The rules live in that file and in `best-practices.md`; this file shows what following them produces, and — in the closing section — which findings were deliberately not written down.

Python here is incidental. The lens is language-agnostic: the same triage, anchors, and phrasing apply to a Rust or shell diff, and only the per-language reference you reach for while judging changes.

## What the reviewer was given

The diff below; the pull-request description, "Fixes double-writes to the refund audit log."; and every call site of `refund` in the repository — two, both in `billing/` — found by search rather than by reading the one package, because the workflow's first step asks for the diff plus enough surrounding context to judge each change.

The description is part of the input. A change that presents itself as a bug fix is judged against principle 2, and the diff either carries the test that failed before it or it does not. The call sites matter for a different reason, visible in the findings below: one concern could be settled by reading them and one could not, and that difference is what decides where each ends up.

```diff
--- a/billing/refunds.py
+++ b/billing/refunds.py
@@ -12,3 +12,14 @@ from billing.audit import RefundAudit
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
- [billing/refunds.py] **principle 2** — the description says this fixes double-writes to the audit log, but the diff *adds* the only `audit.write` in the function and changes nothing about how often it runs, so the duplication it claims to fix is not addressed here and no test would fail without the change. Either the description belongs to a different branch or the fix is missing; say which. When the real fix lands, put one refund through the duplicating path and assert exactly one audit row — two refunds legitimately write two rows, so asserting one across a pair would suppress real history instead of reproducing the defect.

## Should fix (2)

- [billing/refunds.py:13] **principle 5** — the `amount_cents` guard defends against a caller that does not exist: both call sites pass an amount the HTTP layer has already parsed, so nothing reaches `refund` with `None`. Delete it. If untyped input can reach this path by some route the call sites do not show, the check belongs in the handler that admits it, where it can reject with a useful error — the annotation alone would not have settled this, since Python does not enforce it at runtime.
- [billing/refunds.py:24] **principle 16** — `datetime.now(tz=UTC)` is called inside `refund`, so any test asserting on the audit row's timestamp has to patch the clock. Take the timestamp as a parameter and let the caller pass it:

  ```python
  def refund(order_id: OrderId, amount_cents: int, reason: str, now: datetime) -> Refund: ...
  ```

## Could fix (1, optional)

- [billing/refunds.py:22] **principle 21** — `# call the gateway, then write the audit row` names what the next two lines already say. Delete it, or replace it with the reason the audit write is not inside a transaction with the gateway call, if there is one.

## Observations

`actor=reason` reads oddly — `reason` is why the refund happened, and an audit row's actor is usually who caused it. If the audit schema really wants the reason there, the field name is the thing to change; if it wants a user, this is a bug I could not confirm from the diff alone. Not a finding, a question for the author.
````

## Why the review looks like this

- **Two musts lead, and the summary says so in one line.** Triage is the shape of the output, not a note inside it. A reader who stops after the summary still knows the change is blocked and why.
- **The principle 2 finding has no line number.** It is about something absent from the diff, so `[billing/refunds.py]` alone is the honest anchor. Inventing a line to satisfy the format would point at code that is not the problem.
- **It also reads the description as a claim to be checked, not as context.** The stated fix and the shown diff disagree — one adds auditing, the other says it removes duplicate auditing — and noticing that is upstream of noticing the missing test. A description that does not match its diff is a finding on its own; treating it as background is how a branch merges under a summary of work it does not contain.
- **Each finding names the observable thing first** — `order.card_number` reaching the logs, the unreachable `is None` branch — and the principle number second. A reviewer who has never read this skill can still act on all five.
- **The principle 5 finding is confident because someone looked.** The annotation would not have carried it: Python does not enforce `int` at runtime, so "the type says so" is an argument about intent, not about what can arrive. Reading the two call sites is what turned a suspicion into a finding. A reviewer who cannot or will not read them has an Observation, not a `should`.
- **One could, not four.** The diff also uses `result` where the file's other functions use `res`, and the `log.info` call is wrapped in a way `ruff format` would rewrite. Both were dropped: the first matches nothing worth a round trip (principle 9 — the file's local convention wins), and the second is the formatter's job. Stacking those under the card-number finding would cost it attention it needs.
- **The last item is not a finding.** The call sites settled the `is None` question and did not settle this one — whether the audit schema wants an actor or a reason is not answerable from anything the reviewer was given. A concern without a confident anchor goes to Observations as a question rather than into a severity bucket as a verdict. Inventing an anchor to promote it would be the anti-pattern the capability names, and the two items together are the honest shape of a review: what reading further resolved, and what it did not.
