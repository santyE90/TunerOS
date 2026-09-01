# Vehicle model boundaries

## Reference vehicle

The primary future reference is a **2010 BMW E90 335i with the N54 twin-turbo inline-six**. Building
one coherent vehicle first is more valuable than maintaining shallow models of many platforms.
Longer-term engine families may include M52, M54, N52, N54, and N55, but they are not current scope.

## Modeling philosophy

The model will be simplified and internally consistent rather than a full physics simulation. It
should reproduce useful relationships and state transitions without claiming engineering-grade
vehicle fidelity. A future deterministic simulation clock will make runs repeatable, testable, and
independent of wall-clock scheduling. Scenario-driven inputs will eventually describe actions and
conditions such as startup, load changes, and injected faults.

## Units and boundaries

Internal state should use documented canonical units; conversions belong at input, protocol, or
presentation boundaries. Unit choices will be recorded before Phase 1 behavior is implemented.

Every modeled concept must be classifiable as:

1. sourced, public BMW information with a citation;
2. a documented, realistic simplification; or
3. fictional TunerOS simulation behavior.

Names, values, relationships, and messages must not be presented as authentic BMW behavior unless
the supporting source and scope are recorded.

