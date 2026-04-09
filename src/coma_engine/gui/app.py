from __future__ import annotations

import argparse

from coma_engine.config.schema import default_config
from coma_engine.gui.session import GuiSession
from coma_engine.systems.generation import create_world


def build_gui_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python run_gui.py",
        description="Run the Chronicles of Many Ages formal graphical frontend.",
    )
    parser.add_argument("--seed", type=int, default=7, help="Deterministic world seed.")
    parser.add_argument("--debug", action="store_true", help="Open the GUI in debug-grade mode.")
    return parser


def run_gui(argv: list[str] | None = None) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError(
            "PySide6 is required for the formal GUI layer. Install the GUI dependency set before launching run_gui.py."
        ) from exc

    from coma_engine.gui.render.main_window import MainWindow

    args = build_gui_parser().parse_args(argv)
    world = create_world(default_config(seed=args.seed))
    session = GuiSession(world)
    session.set_debug_mode(args.debug)

    app = QApplication(["Chronicles of Many Ages GUI", *(argv or [])])
    window = MainWindow(session)
    window.show()
    return app.exec()
