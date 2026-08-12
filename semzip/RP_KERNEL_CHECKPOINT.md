# RP Kernel 0.1 checkpoint

Local validation before commit:

- 14/14 unit tests passing
- event-sourced world state
- ownership kept distinct from possession
- separate per-character beliefs and memories
- non-witnesses do not receive event knowledge
- memory provenance distinguishes speech from ordinary event memory
- secrets affect planning without being exposed in generated content
- failed actions are recorded without mutating world projections
- response planning is separate from text realization
- long-delay possession memory survives 100 unrelated events

Next experiment: replace only the cheap realizer/interpreter edges while preserving these invariants.
