# Chronicles of Many Ages

Formal simulation engine and formal GUI layer for **Chronicles of Many Ages**.

This repository treats `遊戲製作.md` as the sole design source of truth. The codebase is not a prototype ruleset, a throwaway demo, or an alternative design. The current implementation is organized so the core simulation remains authoritative and every higher layer, including the GUI, sits on top of that core without replacing its semantics.

## Repository layout

- `src/coma_engine/config/`: `ConfigSchema`, phase order, balance parameters
- `src/coma_engine/core/`: `WorldState`, enums, transfer rules, invariant utilities
- `src/coma_engine/models/`: entity models and perception structures
- `src/coma_engine/actions/`: action signatures and formal action catalog
- `src/coma_engine/systems/`: generation, propagation, events, modifiers, relations
- `src/coma_engine/simulation/`: nine-phase execution loop and phase implementations
- `src/coma_engine/player/`: formal player intervention entry points
- `src/coma_engine/explain/`: player-grade and debug-grade explanation services
- `src/coma_engine/gui/`: formal graphical frontend layers
- `tests/`: invariant, projection, visibility, and integration tests

## Core guarantees

- `WorldState` remains the single source of truth
- the fixed nine-phase loop remains authoritative
- actions still resolve through the formal `Action -> Resolution -> ActionOutcome -> Event/Memory/InfoPacket` pipeline
- player interventions still enter through formal channels rather than direct state edits
- GUI projections are read-only, non-authoritative render data
- GUI does not run parallel simulation logic and does not predict outcomes independently of the core

## Implemented systems

- Full nine-phase simulation backbone
- Formal organization layer for `Settlement`, `Faction`, `Polity`, and `WarState`
- Command propagation, local execution variance, skimming, resistance, and consequence logging
- Resource-flow tracing for taxation, remittance, allocation, war supply, and loot
- Demographic aging, birth, death, labor, and combat-population separation
- War support, strain, supply pressure, readiness feedback, and legitimacy-side effects
- Event, memory, and belief-signal propagation with player/debug explanation support
- Player-facing CLI shell for stepping time, inspecting the world, and queuing interventions
- Formal GUI with synchronization, presentation, interaction, rendering, and a five-region game-facing main screen

## Formal GUI layer

The GUI is implemented as a permanent architectural layer, not a temporary prototype. It is structured under `src/coma_engine/gui/` with these responsibilities:

- `sync/`: reads completed `WorldState` steps and builds read-only projections
- `presentation/`: applies player-grade visibility and schema-driven panel mappings
- `interaction/`: captures selection, camera, time control, and intervention intent
- `render/`: draws the map, panels, overlays, and timeline

Current GUI stage coverage:

- GUI session object tied to the existing simulation engine
- Snapshot synchronizer and projection store
- Tile-grid projection, entity projection, timeline projection, and info-flow projection
- Fixed five-region shell: top global bar, left alert/chronicle column, central world viewport, right contextual inspector, bottom action ribbon
- Five named map modes: World, Control, Resources, Pressure, and InfoFlow
- Map readability pass with terrain substrate, polity power cues, pressure hotspots, scarcity/command overlays, and info-flow traces
- Player-grade inspection panels organized as identity, situational summary, structured detail, and contextual affordances
- Alert stack and chronicle stream derived from formal events and projections rather than raw log spam
- Bottom action ribbon that translates legal intervention channels into player-language affordances with non-authoritative previews
- Formal intervention bridge that only queues existing intervention channels
- Qt-based window, map-dominant viewport, top strategic strip, synchronized side columns, and contextual action flow
- Root launcher at `run_gui.py`

## Running the project

Command-line simulation:

```bash
python run_game.py --steps 10 --seed 7
```

Interactive CLI shell:

```bash
python run_game.py --steps 20 --interactive
```

Formal GUI launcher:

```bash
python run_gui.py --seed 7
```

If you want to launch the GUI, install the optional GUI dependency set first:

```bash
pip install .[gui]
```

The current local environment used during development may not include `PySide6`. In that case, `run_gui.py` fails explicitly with a dependency error instead of silently falling back to another interface.

## Interactive CLI commands

- `help`
- `step`
- `map`
- `history`
- `known`
- `npc <npc_id>`
- `settlement <settlement_id>`
- `polity <polity_id>`
- `war <war_id>`
- `why settlement <settlement_id>`
- `why polity <polity_id>`
- `why war <war_id>`
- `bless <npc_id>`
- `resource <tile_or_settlement_id>`
- `rumor <tile_id>`
- `miracle <tile_id>`
- `quit`

## Tests

Run the full validation suite:

```bash
python -m unittest discover -s tests -v
```

The test suite covers:

- replay and phase-order invariants
- bidirectional reference consistency
- command-chain delay, skimming, and consequence paths
- archive-safe organization lifecycle handling
- war supply and war-command feedback
- player knowledge boundaries
- GUI projection invariants
- GUI visibility rules
- GUI intervention bridging
- GUI gameplay-layer main-screen behavior

## Scope

This repository now contains:

- a formally structured core simulation layer
- a player/debug explanation layer
- a minimal playable CLI shell
- the first formal stage of the permanent GUI frontend

Future work can deepen GUI richness, content density, and player-facing affordances, but it should extend this structure rather than replace it.
