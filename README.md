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
- Formal command packets with delivery, delay, distortion, resistance, and execution records
- Local command translation with compliance, softening, resistance, and skimming outcomes
- Persistent archives for dissolved settlements, factions, and polities so history references remain valid
- Active organization mirrors are cleaned on archive while archived objects remain resolvable for history/debug use
- First-pass continuous-action semantics for partial progress, interruption, and outcome recording
- First-pass demographic loop with aging, birth/death records, and labor/combat population separation
- First-pass war loop with attrition, strain, loot capture into settlements, partial remittance to polity treasury, and peace-tension feedback
- Relation templates now enter execution outcomes and command-chain consequences
- Memory conversion now feeds back into formal belief-signal propagation instead of disappearing as dead data
- Formal player intervention queue restricted to approved channels
- Core invariant tests for replayability, reference consistency, political gating, phase snapshots, action interruption, and command-chain delay
- Additional invariant tests for local skimming, archive-safe mirror cleanup, and war-loot remittance

## Quick start

1. Create a Python 3.12 environment.
2. Run the simulation backbone:

```bash
python run_game.py --steps 10 --seed 7
```

3. Run the tests:

```bash
python -m unittest discover -s tests -v
```

## What "running" means right now

This repository can now run the formal simulation backbone from the command line. It also includes a simple interactive shell for stepping the world, printing a map, inspecting entities, and queuing basic player interventions. It is not yet a full graphical game client, so there is no windowed launcher or gameplay UI at this stage.

Interactive shell commands:

- `step`: advance one simulation step
- `map`: print a compact terrain and settlement map
- `npc <npc_id>`: inspect one NPC summary
- `settlement <settlement_id>`: inspect one settlement summary
- `polity <polity_id>`: inspect one polity summary
- `war <war_id>`: inspect one war summary
- `bless <npc_id>`: queue a player modifier intervention
- `resource <tile_or_settlement_id>`: queue a player resource modifier intervention
- `rumor <tile_id>`: queue an information intervention
- `miracle <tile_id>`: queue an event-based intervention
- `quit`: exit the shell

## Current scope

This is a formal backbone, not a content-complete game. The code currently prioritizes system closure and architectural compliance over content breadth, UI, and scenario richness. Several systems are intentionally first-pass implementations with room for deeper expansion, but the structure is designed so future work extends the foundation instead of replacing it.

## Source of truth and launch notes

Use the root launcher so local users do not need to set `PYTHONPATH` manually:

```bash
python run_game.py --steps 10 --seed 7
```

For the interactive shell:

```bash
python run_game.py --steps 20 --interactive
```

The canonical design document for this repository is `遊戲製作.md`. All implementation decisions remain subordinate to that specification rather than inventing a parallel ruleset.
