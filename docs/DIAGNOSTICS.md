# Diagnostics direction

Diagnostics are future scope. The first implementation should be deterministic and rules-based so
each finding can be traced to known inputs and conditions. Machine learning is an optional later
extension, not a substitute for understandable rules.

The planned diagnostic trouble code lifecycle is:

```text
PENDING -> ACTIVE -> HISTORICAL -> CLEARED
```

Exact transition rules, persistence behavior, and reset semantics will be specified before
implementation. When a qualifying fault activates, the system should eventually capture a
freeze-frame snapshot of relevant decoded signals and context. Controlled fault injection should
make lifecycle and diagnostic behavior repeatable without conflating injected symptoms with vehicle
physics.

Predictive diagnostics may later analyze accumulated sessions after deterministic diagnostics and
data quality are established. Phase 1B implements none of these states, rules, records, or APIs.
