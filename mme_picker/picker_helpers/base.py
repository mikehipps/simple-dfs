"""
Picker helper interfaces and shared dataclasses.

These abstractions let the general-purpose FanDuel MME picker share core logic
while each sport provides its own roster definition, scoring nuances, and
summary reporting hooks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ScoreWeights:
    projection: float
    correlation: float
    uniqueness: float
    chalk: float


@dataclass(frozen=True)
class PickerDefaults:
    """Baseline knobs for the greedy selector."""

    n_target: int = 150
    cap_pct: float = 40.0
    max_repeat_init: int = 5
    max_repeat_limit: int = 7
    min_usage_pct: float = 2.0
    breadth_penalty: float = 0.04
    stalled_threshold: int = 3
    selection_window: int = 5000
    weights: ScoreWeights = field(
        default_factory=lambda: ScoreWeights(
            projection=0.55, correlation=0.30, uniqueness=0.30, chalk=0.15
        )
    )


@dataclass(frozen=True)
class PlayerMaps:
    projection: Dict[str, float]
    position: Dict[str, str]
    team: Dict[str, Optional[str]]
    opponent: Dict[str, Optional[str]]
    game: Dict[str, Optional[str]]
    ownership: Dict[str, float]
    name: Dict[str, str]
    roster_order: Dict[str, Optional[str]]
    line: Dict[str, Optional[str]]
    pp_line: Dict[str, Optional[str]]


@dataclass(frozen=True)
class LineupContext:
    players_id: Tuple[str, ...]
    players_txt: Tuple[str, ...]
    slot_columns: Tuple[str, ...]
    slot_labels: Tuple[str, ...]
    player_maps: PlayerMaps
    usage_map: Dict[str, float]


@dataclass(frozen=True)
class LineupFeatures:
    """Sport-specific metrics used in scoring and summaries."""

    correlation_score: float
    extra_score: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SummaryContext:
    selected: Sequence["ScoredLineup"]
    counts: Dict[str, int]
    usage_map: Dict[str, float]
    player_maps: PlayerMaps
    n_target: int


# Forward declaration for type checker; defined in main script.
class ScoredLineup:  # pragma: no cover - satisfied dynamically
    pass


class PickerHelper(ABC):
    """Base contract for sport-specific picker customization."""

    key: str
    name: str
    bonus_tags: Dict[str, Any] = {}

    @property
    @abstractmethod
    def roster_columns(self) -> Sequence[str]:
        """Return the expected column order for roster slots."""

    def defaults(self) -> PickerDefaults:
        """Return sport-specific default tuning parameters."""
        return PickerDefaults()

    def normalize_slot_label(self, column: str) -> str:
        """Collapse duplicate columns like 'WR.1' -> 'WR'."""
        if not column:
            return column
        if "." in column:
            return column.split(".", 1)[0]
        return column

    @abstractmethod
    def compute_lineup_features(self, ctx: LineupContext) -> LineupFeatures:
        """Produce correlation metrics and metadata for a lineup."""

    def summary_lines(self, ctx: SummaryContext) -> List[str]:
        """Optional sport-specific summary rows appended after the generic block."""
        return []

    def after_selection_telemetry(self, lineup: LineupFeatures) -> None:
        """Hook for tracking metrics during selection if needed."""
        _ = lineup

    def configure(self, args: argparse.Namespace) -> None:
        """Hook for helpers to consume runtime arguments."""
        del args


def get_registered_helpers() -> Dict[str, PickerHelper]:
    """Runtime import to avoid circular references."""
    from .nfl import NFLPickerHelper  # noqa: WPS433
    from .nhl import NHLPickerHelper  # noqa: WPS433

    helpers: Dict[str, PickerHelper] = {}
    for helper in (NFLPickerHelper(), NHLPickerHelper()):
        helpers[helper.key] = helper
    return helpers
