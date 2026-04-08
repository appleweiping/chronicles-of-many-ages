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
    archived_settlements: dict[str, Settlement] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)
    archived_factions: dict[str, Faction] = field(default_factory=dict)
    polities: dict[str, Polity] = field(default_factory=dict)
    archived_polities: dict[str, Polity] = field(default_factory=dict)
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
            "command_packet_subjects": {},
            "command_execution_log": [],
            "demographic_log": [],
            "war_log": [],
            "legitimacy_log": [],
            "relation_log": [],
            "belief_log": [],
            "memory_conversion_log": [],
            "local_command_log": [],
            "loot_remittance_log": [],
            "resource_flow_log": [],
            "command_consequence_log": [],
            "packet_deliveries": {},
            "executed_command_packets": set(),
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
        self.archived_settlements = other.archived_settlements
        self.factions = other.factions
        self.archived_factions = other.archived_factions
        self.polities = other.polities
        self.archived_polities = other.archived_polities
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

    def entity_by_ref(self, ref: str) -> object | None:
        registries: dict[str, dict[str, object]] = {
            "tile": self.tiles,
            "npc": self.npcs,
            "settlement": self.settlements | self.archived_settlements,
            "faction": self.factions | self.archived_factions,
            "polity": self.polities | self.archived_polities,
            "war": self.war_states,
            "event": self.events,
            "memory": self.memories,
            "modifier": self.modifiers,
        }
        prefix = ref.split(":", 1)[0]
        registry = registries.get(prefix)
        if registry is None:
            return None
        return registry.get(ref)
