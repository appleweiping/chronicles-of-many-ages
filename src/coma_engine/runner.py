from __future__ import annotations

import argparse

from coma_engine.config.schema import default_config
from coma_engine.explain import (
    debug_grade_step_report,
    player_grade_npc_summary,
    player_grade_polity_summary,
    player_grade_recent_history,
    player_grade_settlement_summary,
    player_grade_world_summary,
)
from coma_engine.player.interventions import (
    queue_information_intervention,
    queue_miracle_intervention,
    queue_npc_modifier_intervention,
    queue_resource_modifier_intervention,
)
from coma_engine.simulation.engine import SimulationEngine
from coma_engine.systems.generation import create_world


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m coma_engine",
        description="Run the Chronicles of Many Ages formal simulation backbone.",
    )
    parser.add_argument("--steps", type=int, default=10, help="How many simulation steps to run.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic world seed.")
    parser.add_argument(
        "--history-limit",
        type=int,
        default=8,
        help="How many recent events to print at the end.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open a simple interactive shell after each step.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show debug-grade action reports after each step.",
    )
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    world = create_world(default_config(seed=args.seed))
    engine = SimulationEngine(world)

    print("Chronicles of Many Ages")
    print(f"Seed: {args.seed}")
    print(f"Initial tiles: {len(world.tiles)}")
    print(f"Initial NPCs: {len(world.npcs)}")
    print(f"Initial settlements: {len(world.settlements)}")
    print(f"Initial factions: {len(world.factions)}")
    print()

    for _ in range(args.steps):
        engine.step()
        for line in player_grade_world_summary(world):
            print(line)
        if args.debug:
            for line in debug_grade_step_report(world, world.current_step - 1):
                print(f"  {line}")
        if args.interactive and not _interactive_shell(world):
            break
        print()

    print()
    print("Recent history:")
    history = player_grade_recent_history(world, limit=args.history_limit)
    if history:
        for line in history:
            print(f"- {line}")
    else:
        print("- No events recorded yet.")

    if world.history_index["errors"]:
        print()
        print("Consistency warnings:")
        for error in world.history_index["errors"][-args.history_limit :]:
            print(f"- {error}")

    return 0


def _interactive_shell(world) -> bool:
    print("Commands: step, map, npc <id>, settlement <id>, polity <id>, war <id>, bless <npc_id>, resource <tile_or_settlement_id>, rumor <tile_id>, miracle <tile_id>, quit")
    while True:
        try:
            raw = input("coma> ").strip()
        except EOFError:
            return False
        if not raw or raw == "step":
            return True
        if raw == "quit":
            return False
        if raw == "map":
            _print_map(world)
            continue
        parts = raw.split()
        if parts[0] == "npc" and len(parts) == 2 and parts[1] in world.npcs:
            for line in player_grade_npc_summary(world, parts[1]):
                print(line)
            continue
        if parts[0] == "settlement" and len(parts) == 2:
            for line in player_grade_settlement_summary(world, parts[1]):
                print(line)
            continue
        if parts[0] == "polity" and len(parts) == 2:
            for line in player_grade_polity_summary(world, parts[1]):
                print(line)
            continue
        if parts[0] == "war" and len(parts) == 2 and parts[1] in world.war_states:
            war = world.war_states[parts[1]]
            print(f"{war.id} participants={war.participant_polity_ids} status={war.status}")
            print(f"front_pressure={war.effective_front_pressure:.1f} attrition={war.expected_attrition:.1f} escalation={war.escalation_risk:.1f}")
            continue
        if parts[0] == "bless" and len(parts) == 2 and parts[1] in world.npcs:
            queue_npc_modifier_intervention(
                world,
                parts[1],
                modifier_type="player_blessing",
                domain="yield.food",
                magnitude=1.0,
                duration=3,
            )
            print("Queued NPC blessing.")
            continue
        if parts[0] == "resource" and len(parts) == 2:
            queue_resource_modifier_intervention(
                world,
                parts[1],
                modifier_type="abundance",
                domain="yield.food",
                magnitude=1.5,
                duration=3,
            )
            print("Queued resource intervention.")
            continue
        if parts[0] == "rumor" and len(parts) == 2:
            queue_information_intervention(
                world,
                content_domain="belief",
                subject_ref=None,
                location_ref=parts[1],
                strength=25.0,
            )
            print("Queued information intervention.")
            continue
        if parts[0] == "miracle" and len(parts) == 2:
            queue_miracle_intervention(
                world,
                event_type="PLAYER_MIRACLE",
                location_ref=parts[1],
                participant_ids=[],
            )
            print("Queued miracle intervention.")
            continue
        print("Unknown command.")


def _print_map(world) -> None:
    by_xy = {(tile.x, tile.y): tile for tile in world.tiles.values()}
    height = world.config.balance_parameters.world_height
    width = world.config.balance_parameters.world_width
    symbols = {"plains": ".", "forest": "F", "hill": "H", "mountain": "M", "water": "~"}
    for y in range(height):
        row = []
        for x in range(width):
            tile = by_xy[(x, y)]
            marker = symbols.get(tile.terrain_type, "?")
            if tile.settlement_id:
                marker = "S"
            row.append(marker)
        print("".join(row))
