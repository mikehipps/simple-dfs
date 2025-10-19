#!/usr/bin/env python3
"""
Crude picker for FanDuel MMA lineups.

Loads projection data and a lineup CSV (IDs only) to compute lineup scores,
usage sums, and uniqueness metrics. Lineups are trimmed using configurable
score/usage thresholds (relative to the medians), then sorted by uniqueness
with an optional per-fighter max-usage cap.

Outputs:
    1. FanDuel-ready lineup CSV (IDs only)
    2. Metrics CSV with scores, usage sums, uniqueness, and player names
    3. Usage summary for the selected lineup pool
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, getcontext
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Sequence, Tuple


# High precision so uniqueness calculations stay finite when usages get tiny.
getcontext().prec = 50


# ---- User-tunable defaults -------------------------------------------------
DEFAULT_TOP_LINEUPS = 150
DEFAULT_SCORE_THRESHOLD = 1.0  # 1.0 -> use the score median as-is
DEFAULT_USAGE_THRESHOLD = 1.0  # 1.0 -> use the usage-sum median as-is
DEFAULT_MAX_USAGE = 0.50       # Max share any fighter can appear across selected lineups

DEFAULT_LINEUPS_INPUT = Path("lineups/mma/fdmma-lineups.csv")
DEFAULT_PROJECTIONS_INPUT = Path("csv-match/inputs/fdmma.csv")
DEFAULT_LINEUPS_OUTPUT = Path("lineups/mma/fdmma-picked.csv")
DEFAULT_METRICS_OUTPUT = Path("lineups/mma/fdmma-picked-metrics.csv")
DEFAULT_USAGE_OUTPUT = Path("lineups/mma/fdmma-picked-usage.csv")


@dataclass
class Projection:
    player_id: str
    name: str
    fppg: float


@dataclass
class LineupMetrics:
    player_ids: Sequence[str]
    score: float
    usage_sum: float
    uniqueness: Decimal


def load_projections(path: Path) -> Dict[str, Projection]:
    projections: Dict[str, Projection] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            player_id = row.get("Id")
            if not player_id:
                continue
            try:
                fppg = float(row.get("FPPG", "").strip() or 0.0)
            except ValueError as exc:
                raise ValueError(f"Could not parse FPPG for player {player_id}") from exc
            first = (row.get("First Name") or "").strip()
            last = (row.get("Last Name") or "").strip()
            nickname = (row.get("Nickname") or "").strip()
            # Prefer nickname when supplied (FanDuel CSVs often duplicate first name there).
            display_name = f"{first} {last}".strip()
            if nickname and nickname not in display_name:
                display_name = f"{nickname} ({display_name})"
            projections[player_id] = Projection(player_id=player_id, name=display_name, fppg=fppg)
    if not projections:
        raise ValueError(f"No projections found in {path}")
    return projections


def load_lineups(path: Path) -> Tuple[List[str], List[List[str]]]:
    lineups: List[List[str]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            raise ValueError(f"{path} is empty or missing a header row")
        header = [cell.strip() for cell in header]
        for row in reader:
            lineup = [cell.strip() for cell in row if cell.strip()]
            if lineup:
                lineups.append(lineup)
    if not lineups:
        raise ValueError(f"No lineups loaded from {path}")
    return header, lineups


def compute_usage(lineups: Iterable[Sequence[str]]) -> Dict[str, Decimal]:
    counts = Counter()
    total_lineups = 0
    for lineup in lineups:
        total_lineups += 1
        counts.update(lineup)
    if total_lineups == 0:
        raise ValueError("Cannot compute usage with zero lineups")
    return {player_id: Decimal(count) / Decimal(total_lineups) for player_id, count in counts.items()}


def build_lineup_metrics(
    lineups: Iterable[Sequence[str]],
    projections: Dict[str, Projection],
    usages: Dict[str, Decimal],
) -> List[LineupMetrics]:
    metrics: List[LineupMetrics] = []
    multipliers = [Decimal("1.5")] + [Decimal("1")] * 5  # MVP slot + five flex spots

    for lineup in lineups:
        if len(lineup) != len(multipliers):
            raise ValueError(f"Unexpected lineup length {len(lineup)}; expected {len(multipliers)}")
        total_score = Decimal("0")
        usage_sum = Decimal("0")
        uniqueness_product = Decimal("1")

        for slot, player_id in enumerate(lineup):
            projection = projections.get(player_id)
            if projection is None:
                raise KeyError(f"Lineup references unknown player id {player_id}")
            multiplier = multipliers[slot]
            total_score += multiplier * Decimal(str(projection.fppg))
            usage = usages.get(player_id)
            if usage is None:
                raise KeyError(f"No usage rate computed for player id {player_id}")
            usage_sum += usage
            uniqueness_product *= usage

        uniqueness_score = Decimal("Infinity") if uniqueness_product == 0 else Decimal("1") / uniqueness_product
        metrics.append(
            LineupMetrics(
                player_ids=tuple(lineup),
                score=float(total_score),
                usage_sum=float(usage_sum),
                uniqueness=uniqueness_score,
            )
        )
    return metrics


def filter_and_select_lineups(
    metrics: Sequence[LineupMetrics],
    top_n: int,
    max_usage: float,
    score_threshold: float,
    usage_threshold: float,
) -> Tuple[List[LineupMetrics], int, float, float]:
    scores = [lineup.score for lineup in metrics]
    usage_sums = [lineup.usage_sum for lineup in metrics]
    score_median = median(scores)
    usage_median = median(usage_sums)
    score_cutoff = score_median * score_threshold
    usage_cutoff = usage_median * usage_threshold

    filtered = [
        lineup
        for lineup in metrics
        if lineup.score >= score_cutoff and lineup.usage_sum >= usage_cutoff
    ]

    filtered.sort(key=lambda lineup: (lineup.uniqueness, lineup.score), reverse=True)

    if max_usage >= 1.0:
        return filtered[:top_n], len(filtered), score_median, usage_median

    if max_usage <= 0:
        raise ValueError("max_usage must be greater than 0 when provided.")

    cap_count = max(1, int(max_usage * top_n))
    counts: Counter[str] = Counter()
    selected: List[LineupMetrics] = []

    for lineup in filtered:
        if len(selected) >= top_n:
            break
        if any(counts[player_id] >= cap_count for player_id in lineup.player_ids):
            continue
        selected.append(lineup)
        counts.update(lineup.player_ids)

    return selected, len(filtered), score_median, usage_median


def write_lineup_csv(
    destination: Path,
    selected: Sequence[LineupMetrics],
    header: Sequence[str],
) -> None:
    with destination.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for lineup in selected:
            if len(header) != len(lineup.player_ids):
                raise ValueError("Output header length does not match lineup length.")
            writer.writerow(list(lineup.player_ids))


def write_metrics_csv(
    destination: Path,
    selected: Sequence[LineupMetrics],
    projections: Dict[str, Projection],
    header: Sequence[str],
) -> None:
    slot_labels: List[str] = []
    occurrences: Counter[str] = Counter()
    for label in header:
        occurrences[label] += 1
        if header.count(label) == 1:
            slot_labels.append(label)
        else:
            slot_labels.append(f"{label}{occurrences[label]}")

    metrics_header = ["Rank", "Score", "UsageSum", "Uniqueness"]
    for label in slot_labels:
        metrics_header.extend([f"{label}_ID", f"{label}_Name"])

    with destination.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(metrics_header)
        for idx, lineup in enumerate(selected, start=1):
            row: List[str] = [
                idx,
                f"{lineup.score:.4f}",
                f"{lineup.usage_sum:.6f}",
                f"{lineup.uniqueness}",
            ]
            for player_id in lineup.player_ids:
                projection = projections.get(player_id)
                name = projection.name if projection else player_id
                row.extend([player_id, name])
            writer.writerow(row)


def write_usage_report(
    destination: Path,
    selected: Sequence[LineupMetrics],
    projections: Dict[str, Projection],
) -> None:
    total_lineups = len(selected)
    if total_lineups == 0:
        raise ValueError("Cannot write usage report without selected lineups")

    counts: Counter[str] = Counter()
    for lineup in selected:
        counts.update(lineup.player_ids)

    header = ["Player ID", "Name", "Times Used", "Usage %"]
    with destination.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for player_id, count in counts.most_common():
            projection = projections.get(player_id)
            name = projection.name if projection else player_id
            usage_pct = (Decimal(count) / Decimal(total_lineups))
            writer.writerow(
                [
                    player_id,
                    name,
                    count,
                    f"{float(usage_pct):.4f}",
                ]
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select MMA lineups by uniqueness after median trims.")
    parser.add_argument(
        "--lineups",
        type=Path,
        default=DEFAULT_LINEUPS_INPUT,
        help="CSV of generated lineups (default: %(default)s)",
    )
    parser.add_argument(
        "--projections",
        type=Path,
        default=DEFAULT_PROJECTIONS_INPUT,
        help="Projection CSV aligned with the lineup field IDs (default: %(default)s)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_LINEUPS,
        help="Number of lineups to return after trimming (default: %(default)s)",
    )
    parser.add_argument(
        "--lineups-output",
        "--output",
        dest="lineups_output",
        type=Path,
        default=DEFAULT_LINEUPS_OUTPUT,
        help="Destination CSV for the selected lineup IDs (default: %(default)s)",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=DEFAULT_METRICS_OUTPUT,
        help="Destination CSV for lineup metrics (default: %(default)s)",
    )
    parser.add_argument(
        "--usage-output",
        type=Path,
        default=DEFAULT_USAGE_OUTPUT,
        help="Destination CSV for usage data derived from selected lineups (default: %(default)s)",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=DEFAULT_SCORE_THRESHOLD,
        help="Multiplier applied to the lineup score median when trimming (default: %(default)s)",
    )
    parser.add_argument(
        "--usage-threshold",
        type=float,
        default=DEFAULT_USAGE_THRESHOLD,
        help="Multiplier applied to the lineup usage-sum median when trimming (default: %(default)s)",
    )
    parser.add_argument(
        "--max-usage",
        type=float,
        default=DEFAULT_MAX_USAGE,
        help="Maximum proportion of selected lineups any single fighter can appear in (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.top <= 0:
        raise ValueError("--top must be a positive integer.")
    if args.score_threshold <= 0:
        raise ValueError("--score-threshold must be greater than 0.")
    if args.usage_threshold <= 0:
        raise ValueError("--usage-threshold must be greater than 0.")
    if not (0 < args.max_usage <= 1):
        raise ValueError("--max-usage must be between 0 and 1.")

    projections = load_projections(args.projections)
    header, lineups = load_lineups(args.lineups)
    usages = compute_usage(lineups)
    metrics = build_lineup_metrics(lineups, projections, usages)
    selected, filtered_count, score_median, usage_median = filter_and_select_lineups(
        metrics,
        args.top,
        args.max_usage,
        args.score_threshold,
        args.usage_threshold,
    )
    score_cutoff = score_median * args.score_threshold
    usage_cutoff = usage_median * args.usage_threshold

    if not selected:
        raise ValueError("No lineups satisfied the median score/usage trim.")

    for output_path in {args.lineups_output, args.metrics_output, args.usage_output}:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    write_lineup_csv(args.lineups_output, selected, header)
    write_metrics_csv(args.metrics_output, selected, projections, header)
    write_usage_report(args.usage_output, selected, projections)

    print(f"Loaded {len(lineups)} lineups from {args.lineups}")
    print(f"Median lineup score: {score_median:.4f} (threshold {score_cutoff:.4f})")
    print(f"Median lineup usage sum: {usage_median:.6f} (threshold {usage_cutoff:.6f})")
    print(f"Trimmed lineup count: {len(metrics)} -> {filtered_count} after applying thresholds")
    if args.max_usage < 1.0:
        print(
            f"Selected lineup count: {filtered_count} -> {len(selected)} "
            f"after applying max usage cap ({args.max_usage:.2%})"
        )
    else:
        print(f"Selected lineup count: {filtered_count} -> {len(selected)} (no usage cap applied)")
    if len(selected) < args.top:
        print(f"Warning: only {len(selected)} lineups remained after trimming (requested {args.top})")
    print(f"Saved {len(selected)} lineups to {args.lineups_output}")
    print(f"Saved lineup metrics to {args.metrics_output}")
    print(f"Saved usage report to {args.usage_output}")


if __name__ == "__main__":
    main()
