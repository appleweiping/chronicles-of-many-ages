from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from random import Random

from coma_engine.actions.models import Action, ActionOutcome
from coma_engine.config.schema import ConfigSchema
from coma_engine.models.entities import (
    Event,
    Faction,
    InfoPacket,
    MemoryEntry,
    Modifier,
    NPC,
    PlayerState,
    Polity,
    Settlement,
    Tile,
    WarState,
)


@dataclass(slots=True)
class WorldState:
    tiles: dict[str, Tile] = field(default_factory=dict)
    npcs: dict[str, NPC] = field(default_factory=dict)
    settlements: dict[str, Settlement] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)
    polities: dict[str, Polity] = field(default_factory=dict)
    war_states: dict[str, WarState] = field(default_factory=dict)
    events: dict[str, Event] = field(default_factory=dict)
    memories: dict[str, MemoryEntry] = field(default_factory=dict)
    info_packets: list[InfoPacket] = field(default_factory=list)
    modifiers: dict[str, Modifier] = field(default_factory=dict)
    action_queue: list[Action] = field(default_factory=list)
    current_step: int = 0
    config: ConfigSchema = field(default_factory=ConfigSchema)
    player_state: PlayerState = field(default_factory=PlayerState)
    history_index: dict[str, object] = field(
        default_factory=lambda: {
            "generated_ids": {},
            "events_by_step": {},
            "outcomes_by_step": {},
            "errors": [],
            "archived_entities": {},
            "dissolved_entities": {},
            "event_layers": {
                "raw_event": [],
                "local_chronicle": [],
                "civilization_node": [],
            },
            "action_explanations": {},
            "command_log": [],
        }
    )
    phase_snapshot_buffer: dict[str, WorldState] = field(default_factory=dict)
    outcome_records: list[ActionOutcome] = field(default_factory=list)
    delayed_effect_queue: list[dict[str, object]] = field(default_factory=list)
    rng: Random = field(default_factory=Random)

    def __post_init__(self) -> None:
        if not self.history_index["generated_ids"]:
            self.rng.seed(self.config.seed)

    def next_id(self, prefix: str) -> str:
        generated_ids: dict[str, int] = self.history_index["generated_ids"]  # type: ignore[assignment]
        generated_ids[prefix] = generated_ids.get(prefix, 0) + 1
        return f"{prefix}:{generated_ids[prefix]}"

    def clone_for_phase(self) -> WorldState:
        clone = deepcopy(self)
        clone.phase_snapshot_buffer = {}
        return clone

    def store_phase_snapshot(self, phase_name: str, snapshot: WorldState) -> None:
        self.phase_snapshot_buffer[phase_name] = snapshot
        retention = self.config.design_constants.phase_snapshot_retention
        if len(self.phase_snapshot_buffer) > retention:
            for key in list(self.phase_snapshot_buffer)[:-retention]:
                del self.phase_snapshot_buffer[key]

    def replace_with(self, other: WorldState) -> None:
        self.tiles = other.tiles
        self.npcs = other.npcs
        self.settlements = other.settlements
        self.factions = other.factions
        self.polities = other.polities
        self.war_states = other.war_states
        self.events = other.events
        self.memories = other.memories
        self.info_packets = other.info_packets
        self.modifiers = other.modifiers
        self.action_queue = other.action_queue
        self.current_step = other.current_step
        self.config = other.config
        self.player_state = other.player_state
        self.history_index = other.history_index
        self.phase_snapshot_buffer = other.phase_snapshot_buffer
        self.outcome_records = other.outcome_records
        self.delayed_effect_queue = other.delayed_effect_queue
        self.rng = other.rng

    def clamp_metric(self, value: float) -> float:
        return max(0.0, min(100.0, value))

    def clamp_probability(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def clamp_resources(self, bundle: dict[str, float]) -> dict[str, float]:
        return {key: max(0.0, float(value)) for key, value in bundle.items()}

    def log_error(self, message: str) -> None:
        errors: list[str] = self.history_index["errors"]  # type: ignore[assignment]
        errors.append(message)

    def record_archived_state(self, ref: str, state: str) -> None:
        archived: dict[str, str] = self.history_index["archived_entities"]  # type: ignore[assignment]
        archived[ref] = state

    def record_dissolved_state(self, ref: str, state: str) -> None:
        dissolved: dict[str, str] = self.history_index["dissolved_entities"]  # type: ignore[assignment]
        dissolved[ref] = state
