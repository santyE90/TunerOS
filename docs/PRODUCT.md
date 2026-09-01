# Product definition

## What TunerOS is

TunerOS is a simulation-first automotive software engineering platform for learning, experimentation,
and portfolio demonstration. It will connect simplified vehicle and ECU behavior to CAN messaging,
telemetry ingestion, datalogging, fault investigation, calibration analysis, and drive-session replay.
Its initial reference is the 2010 BMW E90 335i with the N54 engine.

## Target user

The primary user is a software developer learning automotive, embedded, telematics, or data
engineering concepts. TunerOS should expose system boundaries and data provenance clearly enough to
support study and technical discussion.

## Goals

- Model an understandable end-to-end automotive data path.
- Favor deterministic and testable behavior over visual spectacle.
- Keep components modular enough to replace simulated transport with real hardware later.
- Clearly label sourced BMW concepts, realistic simplifications, and fictional TunerOS behavior.
- Provide useful tools for exploring telemetry, faults, sessions, and calibrations over time.

## Non-goals

TunerOS is not a full vehicle physics engine, a production ECU, a safety-critical diagnostic tool, or
a source of authentic BMW CAN data by default. It will not claim accuracy that its models and sources
cannot support.

## Simulation-first philosophy

The project begins with controlled, repeatable inputs. Future vehicle state will be produced by a
simulation clock and scenario, transformed by simulated ECUs into binary CAN frames, and decoded
before it reaches user-facing systems. This makes each boundary observable while leaving room for a
future transport adapter to accept real frames.

