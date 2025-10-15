#!/usr/bin/env python3
"""
Unified FanDuel MME lineup selector (150-max by default).

Supports multiple sports via sport-specific helper modules. Shared functionality:
    - Loads a FanDuel lineup pool CSV + projections CSV
    - Prunes low-usage players
    - Scores lineups by projection, correlation, uniqueness, and chalkiness
    - Greedy selection with exposure caps and overlap guards
    - Exports selected lineups, usage report, and text summary

Examples:
    python fd_mme_picker.py --sport nhl
    python fd_mme_picker.py --sport nfl --n 150 --cap 45 \
        --lineup-csv lineups/week6.csv --projections-csv projections/week6.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import os
import random
import statistics
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd

from .picker_helpers import (
    LineupContext,
    LineupFeatures,
    PickerHelper,
    PlayerMaps,
    ScoreWeights,
    SummaryContext,
    get_registered_helpers,
)

ID_REGEX = re.compile(r"\(([^)]+)\)\s*$")


def extract_player_id(cell: object) -> str:
    if isinstance(cell, str):
        match = ID_REGEX.search(cell)
        return match.group(1) if match else cell.strip()
    if cell is None:
        return ""
    try:
        if pd.isna(cell):
            return ""
    except (TypeError, ValueError):
        pass
    cell_str = str(cell)
    match = ID_REGEX.search(cell_str)
    return match.group(1) if match else cell_str.strip()


def extract_player_name(cell: object) -> str:
    if isinstance(cell, str):
        idx = cell.rfind("(")
        return cell[:idx].strip() if idx > 0 else cell.strip()
    if cell is None:
        return ""
    try:
        if pd.isna(cell):
            return ""
    except (TypeError, ValueError):
        pass
    cell_str = str(cell)
    idx = cell_str.rfind("(")
    return cell_str[:idx].strip() if idx > 0 else cell_str.strip()


def prompt_with_completion(prompt_text: str, default: Optional[str] = None) -> str:
    try:
        import readline  # type: ignore

        old_completer = readline.get_completer()
        try:
            old_delims = readline.get_completer_delims()
        except AttributeError:
            old_delims = " \t\n"

        def completer(text: str, state: int) -> Optional[str]:
            expanded = os.path.expanduser(text or "")
            matches = sorted(glob.glob(expanded + "*"))
            if state < len(matches):
                candidate = matches[state]
                if os.path.isdir(candidate):
                    candidate += os.sep
                return candidate
            return None

        readline.set_completer_delims(" \t\n")
        readline.parse_and_bind("tab: complete")
        readline.set_completer(completer)
        try:
            value = input(prompt_text).strip()
        finally:
            readline.set_completer(old_completer)
            try:
                readline.set_completer_delims(old_delims)
            except AttributeError:
                pass
        if not value and default:
            return default
        return value
    except (ImportError, AttributeError):
        value = input(prompt_text).strip()
        if not value and default:
            return default
        return value


def browse_for_file(
    title: str, default_dir: Optional[str], filetypes: Optional[Sequence[Tuple[str, str]]]
) -> str:
    try:
        import tkinter as tk
        from tkinter.filedialog import askopenfilename
    except Exception:
        return ""

    root = tk.Tk()
    root.withdraw()
    options = {"title": title}
    if default_dir:
        options["initialdir"] = os.path.expanduser(default_dir)
    if filetypes:
        options["filetypes"] = list(filetypes)
    try:
        path = askopenfilename(**options) or ""
    finally:
        try:
            root.update()
        except Exception:
            pass
        root.destroy()
    return path


def prompt_for_file(label: str, default_dir: Optional[str] = None) -> Path:
    csv_types: Tuple[Tuple[str, str], ...] = (("CSV files", "*.csv"), ("All files", "*.*"))
    prompt_text = f"{label} (Tab to autocomplete, Enter for picker): "
    while True:
        typed = prompt_with_completion(prompt_text)
        if not typed:
            typed = browse_for_file(label, default_dir, csv_types)
            if not typed:
                print("No file selected; please try again.")
                continue
        path = Path(os.path.expanduser(typed)).expanduser()
        if path.exists():
            return path
        print(f"Path not found: {path}")


def resolve_csv_path(initial: Optional[str], label: str, default_dir: Optional[str]) -> Path:
    if initial:
        candidate = Path(initial).expanduser()
        if candidate.exists():
            return candidate
        print(f"{label} not found at {candidate}.")
    print(f"{label} not provided; please choose a file.")
    return prompt_for_file(label, default_dir)


def prompt_for_sport(available: Sequence[str], default: Optional[str]) -> str:
    if default and default in available:
        return default
    print("Available sports:", ", ".join(available))
    while True:
        choice = input("Select sport: ").strip().lower()
        if choice in available:
            return choice
        print("Invalid choice. Please enter one of:", ", ".join(available))


def normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo + 1e-12:
        return [0.0 for _ in values]
    return [(val - lo) / (hi - lo) for val in values]


def compute_pool_usage(lineups_df: pd.DataFrame, roster_cols: Sequence[str]) -> Dict[str, float]:
    counts: Counter[str] = Counter()
    total = len(lineups_df)
    if total == 0:
        return {}
    for _, row in lineups_df.iterrows():
        for col in roster_cols:
            pid = extract_player_id(row[col])
            if pid:
                counts[pid] += 1
    return {pid: cnt / total for pid, cnt in counts.items()}


def unique_players(lineups_df: pd.DataFrame, roster_cols: Sequence[str]) -> Set[str]:
    players: Set[str] = set()
    for _, row in lineups_df.iterrows():
        for col in roster_cols:
            pid = extract_player_id(row[col])
            if pid:
                players.add(pid)
    return players


@dataclass(frozen=True)
class LineupRecord:
    idx: int
    salary: int
    players_id: Tuple[str, ...]
    players_txt: Tuple[str, ...]
    proj_sum: float
    uniq_logsum: float
    chalk_sum: float
    features: LineupFeatures


@dataclass(frozen=True)
class ScoredLineup(LineupRecord):
    score: float


def prune_lineups(
    lineups_df: pd.DataFrame,
    roster_cols: Sequence[str],
    usage_map: Dict[str, float],
    min_usage_frac: float,
) -> Tuple[pd.DataFrame, Dict[str, int], Set[str]]:
    low_players = {pid for pid, pct in usage_map.items() if pct < min_usage_frac}
    n_before = len(lineups_df)
    players_before = len(unique_players(lineups_df, roster_cols))
    if not low_players:
        stats = {
            "n_before": n_before,
            "n_after": n_before,
            "removed_lineups": 0,
            "players_before": players_before,
            "players_after": players_before,
            "removed_players": 0,
        }
        return lineups_df, stats, low_players
    mask = lineups_df[roster_cols].applymap(extract_player_id).isin(low_players).any(axis=1)
    pruned = lineups_df[~mask].reset_index(drop=True)
    players_after = len(unique_players(pruned, roster_cols))
    stats = {
        "n_before": n_before,
        "n_after": len(pruned),
        "removed_lineups": int(mask.sum()),
        "players_before": players_before,
        "players_after": players_after,
        "removed_players": players_before - players_after,
    }
    return pruned, stats, low_players


def detect_projection_columns(df: pd.DataFrame) -> Tuple[str, str, str, Optional[str], Optional[str], Optional[str], Optional[str]]:
    id_col = next((c for c in ["Id", "ID", "PlayerId", "Player_ID", "PLAYER_ID", "player_id"] if c in df.columns), None)
    if not id_col:
        raise ValueError("Could not detect player ID column in projections CSV.")
    proj_col = next((c for c in ["FPPG", "Projection", "Proj", "PROJ", "Fantasy Points"] if c in df.columns), None)
    if not proj_col:
        raise ValueError("Could not detect projection column in projections CSV.")
    pos_col = next((c for c in ["Position", "Pos", "POS"] if c in df.columns), None)
    if not pos_col:
        raise ValueError("Could not detect position column in projections CSV.")
    team_col = next((c for c in ["Team", "TEAM", "team"] if c in df.columns), None)
    opp_col = next((c for c in ["Opponent", "Opp", "OPP"] if c in df.columns), None)
    game_col = next((c for c in ["Game", "Matchup", "MATCHUP", "MatchUp"] if c in df.columns), None)
    own_col = next((c for c in ["Projected Ownership", "Ownership", "OWN", "Own"] if c in df.columns), None)
    return id_col, proj_col, pos_col, team_col, opp_col, game_col, own_col


def load_projections(projections_csv: Path) -> Tuple[pd.DataFrame, Tuple[str, str, str, Optional[str], Optional[str], Optional[str], Optional[str]]]:
    df = pd.read_csv(projections_csv)
    if df.empty:
        raise ValueError("Projections CSV is empty.")
    cols = detect_projection_columns(df)
    if "First Name" in df.columns and "Last Name" in df.columns:
        df["_FullName"] = df["First Name"].astype(str).str.strip() + " " + df["Last Name"].astype(str).str.strip()
    elif "Name" in df.columns:
        df["_FullName"] = df["Name"]
    elif "Player" in df.columns:
        df["_FullName"] = df["Player"]
    return df, cols


def build_player_maps(
    df: pd.DataFrame,
    columns: Tuple[str, str, str, Optional[str], Optional[str], Optional[str], Optional[str]],
) -> PlayerMaps:
    id_col, proj_col, pos_col, team_col, opp_col, game_col, own_col = columns
    proj_map: Dict[str, float] = {}
    pos_map: Dict[str, str] = {}
    team_map: Dict[str, Optional[str]] = {}
    opp_map: Dict[str, Optional[str]] = {}
    game_map: Dict[str, Optional[str]] = {}
    own_map: Dict[str, float] = {}
    name_map: Dict[str, str] = {}
    for _, row in df.iterrows():
        pid_raw = row.get(id_col, "")
        if pd.isna(pid_raw):
            continue
        pid = str(pid_raw).strip()
        if not pid:
            continue
        proj_val = row.get(proj_col, 0.0)
        proj_map[pid] = float(proj_val) if pd.notna(proj_val) else 0.0
        pos_val = row.get(pos_col, "")
        pos_map[pid] = str(pos_val).strip() if pd.notna(pos_val) else ""
        team_val = row.get(team_col) if team_col else None
        opp_val = row.get(opp_col) if opp_col else None
        game_val = row.get(game_col) if game_col else None
        team_map[pid] = str(team_val).strip() if team_val and pd.notna(team_val) else None
        opp_map[pid] = str(opp_val).strip() if opp_val and pd.notna(opp_val) else None
        game_map[pid] = str(game_val).strip() if game_val and pd.notna(game_val) else None
        if own_col:
            own_val = row.get(own_col, None)
            if pd.notna(own_val):
                own_map[pid] = float(own_val)
        name_val = row.get("_FullName", None)
        if pd.notna(name_val):
            name_map[pid] = str(name_val).strip()
    return PlayerMaps(
        projection=proj_map,
        position=pos_map,
        team=team_map,
        opponent=opp_map,
        game=game_map,
        ownership=own_map,
        name=name_map,
    )


def make_lineup_records(
    lineups_df: pd.DataFrame,
    roster_cols: Sequence[str],
    helper: PickerHelper,
    player_maps: PlayerMaps,
    usage_map: Dict[str, float],
) -> List[LineupRecord]:
    records: List[LineupRecord] = []
    slot_labels = [helper.normalize_slot_label(col) for col in roster_cols]
    for idx, row in lineups_df.iterrows():
        players_txt = tuple(str(row[col]) for col in roster_cols)
        players_id = tuple(extract_player_id(row[col]) for col in roster_cols)
        salary_val = row.get("Budget", row.get("Salary", 0))
        salary = int(salary_val) if pd.notna(salary_val) else 0
        proj_sum = sum(player_maps.projection.get(pid, 0.0) for pid in players_id)
        uniq_logsum = 0.0
        chalk_sum = 0.0
        for pid in players_id:
            usage = usage_map.get(pid, 1e-6)
            usage = max(usage, 1e-6)
            uniq_logsum += -math.log(usage)
            chalk_sum += usage
        ctx = LineupContext(
            players_id=players_id,
            players_txt=players_txt,
            slot_columns=tuple(roster_cols),
            slot_labels=tuple(slot_labels),
            player_maps=player_maps,
            usage_map=usage_map,
        )
        features = helper.compute_lineup_features(ctx)
        records.append(
            LineupRecord(
                idx=idx,
                salary=salary,
                players_id=players_id,
                players_txt=players_txt,
                proj_sum=proj_sum,
                uniq_logsum=uniq_logsum,
                chalk_sum=chalk_sum,
                features=features,
            )
        )
    return records


def passes_caps(
    lineup: LineupRecord,
    selected: Sequence[ScoredLineup],
    counts: Dict[str, int],
    cap_count: int,
    max_repeat: int,
    seen_sets: Set[frozenset],
) -> bool:
    for pid in lineup.players_id:
        if counts.get(pid, 0) + 1 > cap_count:
            return False
    lineup_set = frozenset(lineup.players_id)
    if lineup_set in seen_sets:
        return False
    if max_repeat < len(lineup.players_id):
        current_players = set(lineup.players_id)
        for chosen in selected:
            overlap = sum(1 for pid in chosen.players_id if pid in current_players)
            if overlap > max_repeat:
                return False
    return True


def greedy_select(
    records: Sequence[LineupRecord],
    weights: ScoreWeights,
    n_target: int,
    cap_pct: float,
    max_repeat_init: int,
    max_repeat_limit: int,
    breadth_penalty: float,
    selection_window: int,
    stalled_threshold: int,
    seed: Optional[int],
) -> Tuple[List[ScoredLineup], Dict[str, int], Dict[str, float]]:
    if seed is not None:
        random.seed(seed)
    cap_count = max(1, int(math.floor((cap_pct / 100.0) * n_target + 1e-9)))
    proj_list = [rec.proj_sum for rec in records]
    corr_list = [rec.features.correlation_score for rec in records]
    uniq_list = [rec.uniq_logsum for rec in records]
    chalk_list = [rec.chalk_sum for rec in records]
    extra_list = [rec.features.extra_score for rec in records]
    proj_norm = normalize(proj_list)
    corr_norm = normalize(corr_list)
    uniq_norm = normalize(uniq_list)
    chalk_norm = normalize(chalk_list)

    score_entries = []
    score_lookup: Dict[int, float] = {}
    for idx, rec in enumerate(records):
        score = (
            weights.projection * proj_norm[idx]
            + weights.correlation * corr_norm[idx]
            + weights.uniqueness * uniq_norm[idx]
            - weights.chalk * chalk_norm[idx]
            + extra_list[idx]
        )
        score_entries.append((score, random.random(), idx))
        score_lookup[idx] = score
    score_entries.sort(key=lambda x: (x[0], x[1]), reverse=True)
    order = [idx for _, _, idx in score_entries]
    window = min(selection_window, len(order)) if selection_window > 0 else len(order)

    selected: List[ScoredLineup] = []
    counts: Dict[str, int] = {}
    seen_sets: Set[frozenset] = set()
    max_repeat = max_repeat_init
    relaxations = 0
    pointer = 0
    stalled = 0

    while len(selected) < n_target and pointer < len(order):
        batch = order[pointer : pointer + window]
        best_idx: Optional[int] = None
        best_score = float("-inf")
        for idx in batch:
            rec = records[idx]
            if not passes_caps(rec, selected, counts, cap_count, max_repeat, seen_sets):
                continue
            penalty = 0.0
            for pid in rec.players_id:
                filled = counts.get(pid, 0) / cap_count
                penalty += filled * filled
            score = score_lookup[idx] - breadth_penalty * penalty
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is not None:
            rec = records[best_idx]
            selected.append(ScoredLineup(**rec.__dict__, score=best_score))
            seen_sets.add(frozenset(rec.players_id))
            for pid in rec.players_id:
                counts[pid] = counts.get(pid, 0) + 1
            stalled = 0
            if len(selected) % 10 == 0 or len(selected) == n_target:
                print(f"  Selected {len(selected)}/{n_target} lineups…")
        else:
            stalled += 1
            if stalled_threshold > 0 and stalled >= stalled_threshold and max_repeat < max_repeat_limit:
                max_repeat += 1
                relaxations += 1
                stalled = 0
            else:
                pointer += window

    diag = {
        "cap_pct": cap_pct,
        "cap_count": cap_count,
        "max_repeat_start": max_repeat_init,
        "max_repeat_final": max_repeat,
        "repeat_relaxations": relaxations,
        "picked": len(selected),
        "target": n_target,
        "lineups_considered": len(records),
        "selection_window": window,
    }
    return selected, counts, diag


def export_selected_lineups(
    lineups_df: pd.DataFrame,
    roster_cols: Sequence[str],
    selected: Sequence[LineupRecord],
    output_csv: Path,
) -> None:
    if not selected:
        return
    indices = [lu.idx for lu in selected]
    subset = lineups_df.iloc[indices].copy().reset_index(drop=True)
    for col in roster_cols:
        subset[col] = subset[col].apply(extract_player_id)
    headers = []
    for col in subset.columns:
        if "." in str(col):
            headers.append(str(col).split(".", 1)[0])
        else:
            headers.append(str(col))
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(subset.to_numpy())


def export_usage_report(
    counts: Dict[str, int],
    usage_map: Dict[str, float],
    player_maps: PlayerMaps,
    n_target: int,
    output_csv: Path,
) -> None:
    if not counts:
        return
    rows = []
    fieldnames = [
        "Player",
        "Player ID",
        "Position",
        "Team",
        "Selected Lineups",
        "Selected %",
        "Pool %",
        "Delta %",
        "Proj FPPG",
        "Proj Ownership",
    ]
    for pid, cnt in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        selected_pct = 100.0 * cnt / max(1, n_target)
        pool_pct = 100.0 * usage_map.get(pid, 0.0)
        delta = selected_pct - pool_pct
        proj = player_maps.projection.get(pid, 0.0)
        own_val = player_maps.ownership.get(pid)
        pos = player_maps.position.get(pid, "")
        team = player_maps.team.get(pid) or ""
        name = player_maps.name.get(pid) or pid
        rows.append(
            {
                "Player": name,
                "Player ID": pid,
                "Position": pos,
                "Team": team,
                "Selected Lineups": cnt,
                "Selected %": f"{selected_pct:.1f}",
                "Pool %": f"{pool_pct:.1f}",
                "Delta %": f"{delta:+.1f}",
                "Proj FPPG": f"{proj:.2f}",
                "Proj Ownership": f"{own_val:.1f}" if own_val is not None else "",
            }
        )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize_selection(
    helper: PickerHelper,
    selected: Sequence[ScoredLineup],
    counts: Dict[str, int],
    usage_map: Dict[str, float],
    player_maps: PlayerMaps,
    diag: Dict[str, float],
    pool_before: int,
    pool_after: int,
    prune_stats: Optional[Dict[str, int]],
    low_players: Set[str],
    n_target: int,
    min_usage_pct: float,
) -> List[str]:
    lines: List[str] = []
    lines.append(
        f"{helper.name} picker selected {len(selected)}/{n_target} lineups (pool before={pool_before}, after={pool_after})."
    )
    if prune_stats and prune_stats.get("removed_lineups", 0):
        lines.append(
            f"Pruned {prune_stats['removed_lineups']} lineups ({len(low_players)} low-usage players < {min_usage_pct:.2f}%)."
        )
    lines.append(
        f"Exposure cap {diag['cap_pct']:.1f}% → {diag['cap_count']} lineups, overlap {diag['max_repeat_start']} → {diag['max_repeat_final']} (relaxed {diag['repeat_relaxations']}x)."
    )
    if diag["picked"] < n_target:
        lines.append("WARNING: Could not fill the full target under current caps/overlap settings.")
    if selected:
        proj_values = [lu.proj_sum for lu in selected]
        lines.append(
            f"Projection avg {statistics.mean(proj_values):.2f}, median {statistics.median(proj_values):.2f}, range {min(proj_values):.2f}-{max(proj_values):.2f}."
        )
    context = SummaryContext(
        selected=selected,
        counts=counts,
        usage_map=usage_map,
        player_maps=player_maps,
        n_target=n_target,
    )
    lines.extend(helper.summary_lines(context))

    players_at_cap = [pid for pid, cnt in counts.items() if cnt >= diag["cap_count"]]
    if players_at_cap:
        lines.append(f"Players at cap ({len(players_at_cap)}): " + ", ".join(players_at_cap))
    lines.append("Top exposures (selected% | pool% | Δ | POS | TEAM | player [id] | proj | own):")
    top_exposures = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:12]
    for pid, cnt in top_exposures:
        selected_pct = 100.0 * cnt / max(1, n_target)
        pool_pct = 100.0 * usage_map.get(pid, 0.0)
        delta = selected_pct - pool_pct
        proj_val = player_maps.projection.get(pid, 0.0)
        own_val = player_maps.ownership.get(pid)
        pos = player_maps.position.get(pid, "")
        team = player_maps.team.get(pid) or ""
        name = player_maps.name.get(pid) or pid
        line = (
            f"  {selected_pct:5.1f}% | {pool_pct:5.1f}% | {delta:+5.1f} | {pos:<3} | {team:<3} | {name} [{pid}] | {proj_val:5.2f}"
        )
        if own_val is not None:
            line += f" | {own_val:4.1f}%"
        lines.append(line)
    return lines


def parse(args: Optional[List[str]], default_sport: Optional[str]) -> argparse.Namespace:
    helpers = get_registered_helpers()
    prelim = argparse.ArgumentParser(add_help=False)
    prelim.add_argument("--sport", "-s")
    known, remaining = prelim.parse_known_args(args)
    sport = (known.sport or default_sport or "").lower()
    if sport and sport not in helpers:
        print(f"Unknown sport '{sport}'. Available: {', '.join(sorted(helpers))}")
        sport = ""
    if not sport:
        sport = prompt_for_sport(sorted(helpers), default_sport)
    known.sport = sport
    helper = helpers[sport]
    parser = argparse.ArgumentParser(description="General-purpose FanDuel MME lineup picker.")
    parser.add_argument("--sport", "-s", default=sport, choices=sorted(helpers))
    parser.add_argument("lineup_csv", nargs="?", default=None)
    parser.add_argument("projections_csv", nargs="?", default=None)
    parser.add_argument("--n", type=int, help="How many lineups to select.")
    parser.add_argument("--cap", type=float, help="Max exposure per player (percent).")
    parser.add_argument("--max-repeat", type=int, help="Initial max shared players between lineups.")
    parser.add_argument("--max-repeat-limit", type=int, help="Maximum overlap after relaxations.")
    parser.add_argument("--min-usage-pct", type=float, help="Prune players below this pool usage.")
    parser.add_argument("--breadth-penalty", type=float, help="Penalty factor for near-cap players.")
    parser.add_argument("--selection-window", type=int, help="Top candidate window per sweep.")
    parser.add_argument("--stalled-threshold", type=int, help="Failed sweeps before relaxing overlap.")
    parser.add_argument("--w-proj", type=float, help="Weight for projection.")
    parser.add_argument("--w-corr", type=float, help="Weight for correlation bonus.")
    parser.add_argument("--w-uniq", type=float, help="Weight for uniqueness/entropy.")
    parser.add_argument("--w-chalk", type=float, help="Penalty weight for chalkiness.")
    parser.add_argument("--seed", type=int, help="Optional RNG seed.")
    parser.add_argument("--out-prefix", help="Filename prefix for outputs (default derived from lineup CSV).")
    parser.add_argument("--out-dir", default="autoFD", help="Directory for outputs (default: autoFD).")
    return parser.parse_args(remaining, namespace=known)


def apply_defaults(args: argparse.Namespace, helper: PickerHelper) -> Tuple[argparse.Namespace, ScoreWeights]:
    defaults = helper.defaults()
    weights = defaults.weights
    args.n = args.n or defaults.n_target
    args.cap = args.cap if args.cap is not None else defaults.cap_pct
    args.max_repeat = args.max_repeat or defaults.max_repeat_init
    args.max_repeat_limit = args.max_repeat_limit or defaults.max_repeat_limit
    args.min_usage_pct = args.min_usage_pct if args.min_usage_pct is not None else defaults.min_usage_pct
    args.breadth_penalty = args.breadth_penalty if args.breadth_penalty is not None else defaults.breadth_penalty
    args.selection_window = args.selection_window or defaults.selection_window
    args.stalled_threshold = args.stalled_threshold or defaults.stalled_threshold
    proj_weight = args.w_proj if args.w_proj is not None else weights.projection
    corr_weight = args.w_corr if args.w_corr is not None else weights.correlation
    uniq_weight = args.w_uniq if args.w_uniq is not None else weights.uniqueness
    chalk_weight = args.w_chalk if args.w_chalk is not None else weights.chalk
    score_weights = ScoreWeights(
        projection=proj_weight,
        correlation=corr_weight,
        uniqueness=uniq_weight,
        chalk=chalk_weight,
    )
    return args, score_weights


def main(argv: Optional[List[str]] = None, *, default_sport: Optional[str] = None) -> None:
    args = parse(argv, default_sport)
    helpers = get_registered_helpers()
    helper = helpers[args.sport]
    args, score_weights = apply_defaults(args, helper)

    if args.out_dir == "autoFD":
        args.out_dir = "autoNHL" if helper.key == "nhl" else "autoMME"

    lineup_path = resolve_csv_path(args.lineup_csv, "Lineup CSV", "lineups")
    projections_path = resolve_csv_path(args.projections_csv, "Projections CSV", "projections-csv")

    print(f"Loading lineup pool from {lineup_path}…")
    lineups_df = pd.read_csv(lineup_path)
    roster_cols = list(helper.roster_columns)
    missing = [col for col in roster_cols if col not in lineups_df.columns]
    if missing:
        raise ValueError(f"Lineup CSV missing required columns: {missing}")
    print(f"Loaded {len(lineups_df)} candidate lineups with roster columns {roster_cols}.")

    pool_before = len(lineups_df)
    usage_map = compute_pool_usage(lineups_df, roster_cols)
    min_usage_frac = max(0.0, args.min_usage_pct / 100.0) if args.min_usage_pct else 0.0
    prune_stats: Optional[Dict[str, int]] = None
    low_players: Set[str] = set()
    if min_usage_frac > 0.0:
        print(f"Pruning lineups using players below {args.min_usage_pct:.2f}% pool usage…")
        lineups_df, prune_stats, low_players = prune_lineups(lineups_df, roster_cols, usage_map, min_usage_frac)
        usage_map = compute_pool_usage(lineups_df, roster_cols)
    else:
        usage_map = compute_pool_usage(lineups_df, roster_cols)
    if lineups_df.empty:
        raise ValueError("No candidate lineups remain after pruning.")

    print(f"Loading projections from {projections_path}…")
    proj_df, proj_columns = load_projections(projections_path)
    player_maps = build_player_maps(proj_df, proj_columns)

    print("Constructing lineup objects for scoring…")
    records = make_lineup_records(lineups_df, roster_cols, helper, player_maps, usage_map)
    if not records:
        raise ValueError("Failed to build lineup records from the pool.")

    print("Running greedy lineup selection…")
    selected, counts, diag = greedy_select(
        records=records,
        weights=score_weights,
        n_target=args.n,
        cap_pct=args.cap,
        max_repeat_init=args.max_repeat,
        max_repeat_limit=args.max_repeat_limit,
        breadth_penalty=args.breadth_penalty,
        selection_window=args.selection_window if len(records) > args.selection_window else len(records),
        stalled_threshold=args.stalled_threshold,
        seed=args.seed,
    )
    if not selected:
        raise RuntimeError("Selector could not find any lineups under the given constraints.")
    print(f"Selected {len(selected)} lineups (target {args.n}).")

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.out_prefix or f"{helper.key}_{lineup_path.stem}"
    selected_path = out_dir / f"{prefix}_selected_lineups.csv"
    usage_path = out_dir / f"{prefix}_usage_report.csv"
    summary_path = out_dir / f"{prefix}_summary.txt"

    print(f"Writing selected lineups to {selected_path}…")
    export_selected_lineups(lineups_df, roster_cols, selected, selected_path)
    print(f"Writing usage report to {usage_path}…")
    export_usage_report(counts, usage_map, player_maps, args.n, usage_path)

    summary_lines = summarize_selection(
        helper=helper,
        selected=selected,
        counts=counts,
        usage_map=usage_map,
        player_maps=player_maps,
        diag=diag,
        pool_before=pool_before,
        pool_after=len(lineups_df),
        prune_stats=prune_stats,
        low_players=low_players,
        n_target=args.n,
        min_usage_pct=args.min_usage_pct or 0.0,
    )
    print(f"Writing summary to {summary_path}…")
    summary_path.write_text("\n".join(summary_lines))
    for line in summary_lines:
        print(line)


if __name__ == "__main__":
    main()
