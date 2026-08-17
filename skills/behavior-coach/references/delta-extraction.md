# Delta Extraction

Stage 4: turn two transcript sets (source, baseline) into a short list of classified deltas. This is the filter that keeps the produced skill lean — everything downstream is authored from this table and nothing else.

## The diff

For each scoped dimension, lay the source and baseline transcripts side by side and ask one question: **what did the source do here that the baseline didn't, and did it move anything a scoped dimension observes — the evidence trail, the failure shape, the final result?**

- Same behavior in both → discard. The target already does it; encoding it is dead weight.
- Different behavior, no change to any scoped observable → discard. Style, not process.
- Different behavior that changes a scoped observable or the failure shape → a candidate delta. Record it — a matching final task result does not disqualify it: a target that guesses its way to the same working endpoint the source verified still carries the verification gap, and luck is not process.

Record each candidate as one row:

```text
DIMENSION:   verification
SOURCE DID:  stated "done means: curl /health returns 200" before starting; pasted the curl output before claiming done
BASELINE DID: claimed "everything should work now" with no command run after the last edit
OUTCOME GAP: baseline's claim was false — the route 404'd; source's claim was checked
RATIONALIZATION (baseline, verbatim): "the pieces are all correct, so it should work"
PROVENANCE:  observed (2/2 runs) | vendor-documented | community-reported | self-reported
```

## Classification

Every candidate delta gets exactly one class. The class decides its fate in stage 5.

| Class | Test | Fate |
| --- | --- | --- |
| **PORTABLE** | The behavior can be restated as a decision rule whose compliance is checkable from the transcript alone, and following it requires no capability the target lacks | Encoded as a rule in the produced skill |
| **PARTIAL** | The behavior depends on a judgment call the target makes worse than the source ("notice when the output contradicts the plan") | Encode only if you can attach a **mechanical trigger** that removes the judgment ("compare the checkpoint output against the expectation written in the plan; any mismatch is a surprise"). No trigger found → treat as non-portable. |
| **NON-PORTABLE** | The behavior _is_ capability — deeper reasoning, longer coherence, knowledge the target lacks | Never encoded as a rule. Listed in the produced skill's honest-limits note. |

The PARTIAL class is where distillations succeed or fail. The source often doesn't follow a rule — it just _notices_ things. The craft is converting each noticing into a check: "notice the diagnosis is wrong" becomes "count fix attempts per failing check; at two, the diagnosis is wrong — stop patching."

## Provenance gates

- `observed` (majority of runs) — encode freely.
- `vendor-documented` — encode freely; cite the document in the distillation notes.
- `self-reported` — encode only after a task probe corroborates it (then it becomes `observed`).
- `community-reported` — encode only with a second independent source (a corroborating observation or vendor document).

## Output of this stage

A single table of classified deltas plus the verbatim rationalization list, ordered by outcome impact. Aim for **5–15 portable rows total** — more than that usually means the diff kept style differences, or the scope (stage 1) took on too many dimensions. Cut from the bottom before authoring.
