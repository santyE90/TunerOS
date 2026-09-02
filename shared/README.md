# Shared contracts

This directory will hold deliberately language-neutral contracts or fixtures when more than one
TunerOS component needs them. It remains empty in Phase 2B: the raw frame contract is represented by
C++ and Python value objects at their respective boundaries, while independent JSON golden vectors
under `tests/fixtures/` verify compatibility without creating a generated shared schema prematurely.
