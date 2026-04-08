# Chronicles of Many Ages

Formal core simulation backbone for **Chronicles of Many Ages**.

This repository implements the first-pass formal systems foundation described in `遊戲製作.md`. The goal is not a throwaway demo. The current codebase is structured around the document's required constraints:

- `WorldState` as the single source of truth
- fixed nine-phase simulation loop with snapshot semantics
- formal `Action -> Resolution -> ActionOutcome -> Event/Memory/Modifier/InfoPacket` pipeline
- bounded `PerceivedState` channels instead of omniscient NPC reads
- explicit `Settlement / Faction / Polity / WarState` organization layer
- unified transfer interfaces for bidirectional references
- player interventions restricted to formal `Modifier / InfoPacket / Event` channels

## Repository layout

- `src/coma_engine/config/`: `ConfigSchema`, design constants, balance parameters
- `src/coma_engine/core/`: `WorldState`, enums, transfer and mirror-consistency utilities
- `src/coma_engine/models/`: core entity models and perceived-state channels
- `src/coma_engine/actions/`: formal action structures, signatures, action catalog
- `src/coma_engine/systems/`: generation, propagation, modifiers, events, relations, spatial helpers
- `src/coma_engine/simulation/`: phase implementations and the simulation engine
- `src/coma_engine/player/`: formal player intervention entry points
- `src/coma_engine/scenario/`: scenario-layer placeholder interfaces
- `src/coma_engine/explain/`: debug-grade and player-grade explanation services
- `tests/`: deterministic and invariant-oriented foundation tests

## Implemented foundation

- Typed world model for `Tile`, `NPC`, `Settlement`, `Faction`, `Polity`, `WarState`, `Event`, `MemoryEntry`, `InfoPacket`, `Modifier`, `PlayerState`, and `Objective`
- Fixed phase order:
  `EnvironmentPhase`, `ResourcePhase`, `NeedUpdatePhase`, `InformationPhase`, `DecisionPhase`, `DeclarationPhase`, `ResolutionPhase`, `PoliticalPhase`, `EventPhase`
- Resolution substeps:
  validity check, resource reservation, contest resolution, effect application, cleanup/hooks
- Initial world generation with tiles, NPCs, early settlement/faction seeding
- Reference reconciliation and mirror validation for ownership and membership links
- Event materialization from action outcomes with derived memories and info packets
- Formal player intervention queue restricted to approved channels
- Core invariant tests for replayability, reference consistency, political gating, and phase snapshots

## Quick start

1. Create a Python 3.12 environment.
2. Run the simulation backbone:

```bash
python -m coma_engine --steps 10 --seed 7
```

3. Run the tests:

```bash
python -m unittest discover -s tests -v
```

## What "running" means right now

This repository can now run the formal simulation backbone from the command line. It is not yet a full graphical game client, so there is no windowed launcher or gameplay UI at this stage.

## Current scope

This is a formal backbone, not a content-complete game. The code currently prioritizes system closure and architectural compliance over content breadth, UI, and scenario richness. Several systems are intentionally first-pass implementations with room for deeper expansion, but the structure is designed so future work extends the foundation instead of replacing it.

## Source of truth

The design source of truth for this repository is `遊戲製作.md`. When extending the project, implementation decisions should remain subordinate to that specification rather than inventing a parallel ruleset.
