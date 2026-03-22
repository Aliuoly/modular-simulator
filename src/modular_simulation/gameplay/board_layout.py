"""Service-owned board-layout state for render metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


Point2D = tuple[float, float]


@dataclass(frozen=True)
class UnitEntityLayout:
    process_id: str
    anchor_xy: Point2D


@dataclass(frozen=True)
class LineEntityLayout:
    line_id: str
    source: str
    target: str
    path_xy: tuple[Point2D, ...]


@dataclass
class BoardLayoutRuntime:
    _unit_entities_by_process_id: dict[str, UnitEntityLayout] = field(default_factory=dict)
    _line_entities_by_line_id: dict[str, LineEntityLayout] = field(default_factory=dict)
    _next_line_index: int = 1

    def place_unit(self, *, process_id: str, anchor_xy: Point2D) -> None:
        self._unit_entities_by_process_id[process_id] = UnitEntityLayout(
            process_id=process_id,
            anchor_xy=(float(anchor_xy[0]), float(anchor_xy[1])),
        )

    def add_line(
        self,
        *,
        source: str,
        target: str,
        path_xy: tuple[Point2D, ...],
        line_id: str | None = None,
    ) -> str:
        selected_line_id = line_id or f"line_{self._next_line_index}"
        if line_id is None:
            self._next_line_index += 1
        self._line_entities_by_line_id[selected_line_id] = LineEntityLayout(
            line_id=selected_line_id,
            source=source,
            target=target,
            path_xy=tuple((float(x), float(y)) for x, y in path_xy),
        )
        return selected_line_id

    def as_payload(self) -> Mapping[str, object]:
        return {
            "unit_entities_by_process_id": {
                process_id: {
                    "process_id": entity.process_id,
                    "anchor_xy": entity.anchor_xy,
                }
                for process_id, entity in self._unit_entities_by_process_id.items()
            },
            "line_entities_by_line_id": {
                line_id: {
                    "line_id": entity.line_id,
                    "source": entity.source,
                    "target": entity.target,
                    "path_xy": entity.path_xy,
                }
                for line_id, entity in self._line_entities_by_line_id.items()
            },
        }
