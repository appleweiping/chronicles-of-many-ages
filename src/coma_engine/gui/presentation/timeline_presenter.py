from __future__ import annotations

from collections import defaultdict

from coma_engine.gui.types import TimelineEntryProjection


def group_timeline_entries(entries: tuple[TimelineEntryProjection, ...]) -> dict[str, list[TimelineEntryProjection]]:
    grouped: dict[str, list[TimelineEntryProjection]] = defaultdict(list)
    for entry in entries:
        if entry.visibility in {"rumored", "inferred"}:
            grouped["signals:rumor"].append(entry)
            continue
        importance_band = "major" if entry.importance >= 70.0 else "notable" if entry.importance >= 45.0 else "minor"
        grouped[f"{entry.layer}:{importance_band}"].append(entry)
    return dict(grouped)
