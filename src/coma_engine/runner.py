from __future__ import annotations

import argparse

from coma_engine.config.schema import default_config
from coma_engine.explain.service import player_grade_recent_history
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
        print(
            f"Step {world.current_step}: "
            f"settlements={len(world.settlements)} "
            f"factions={len(world.factions)} "
            f"polities={len(world.polities)} "
            f"wars={len(world.war_states)} "
            f"events={len(world.events)}"
        )

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
