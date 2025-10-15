#!/usr/bin/env python3
"""
FanDuel NHL lineup picker (150-max default)

Usage example:
    python3 fdnhl_picker.py lineups/10142025-1748-10000-fd-lineups-hockey-lineups.csv \
        projections-csv/nhl1014.csv --out-prefix nhl1014 --out-dir autoNHL

The script scores the lineup pool on projections, correlation heuristics, and
player-usage uniqueness, then greedily builds a capped-exposure set.
"""

import argparse
import csv
import glob
import math
import os
import random
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
import re

import pandas as pd

DEFAULT_N_TARGET = 150
DEFAULT_CAP_PCT = 30.0
DEFAULT_MAX_REPEAT_INIT = 5
DEFAULT_MAX_REPEAT_LIMIT = 6
DEFAULT_SELECTION_WINDOW = 1000
DEFAULT_BREADTH_PENALTY = 0.045
DEFAULT_STALLED_THRESHOLD = 3
DEFAULT_MIN_USAGE_PCT = 1.0  # percent of pool appearances
DEFAULT_W_PROJ = 0.45
DEFAULT_W_CORR = 0.50
DEFAULT_W_UNIQ = 0.35
DEFAULT_W_CHALK = 0.20

NON_ROSTER_LABELS = {
    "BUDGET", "SALARY", "FPPG", "PROJECTION", "PROJECTIONS", "PROJ", "TOTAL",
    "TOTALFPPG", "TOTAL FPPG", "TOTAL_PROJ", "RANK", "LINEUP", "LINEUP ID",
    "LINEUPID", "STACK", "NOTES", "OWN", "OWNERSHIP", "CEILING", "FLOOR",
    "VALUE", "TEAM", "TEAMS", "TITLE"
}

ID_REGEX = re.compile(r"\(([^)]+)\)\s*$")


def extract_player_id(cell: object) -> str:
    if isinstance(cell, str):
        match = ID_REGEX.search(cell)
        return match.group(1) if match else cell.strip()
    if cell is None:
        return ""
    try:
        # Handle pandas Series/DataFrame case
        if hasattr(cell, 'empty'):
            return ""
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
        # Handle pandas Series/DataFrame case
        if hasattr(cell, 'empty'):
            return ""
        if pd.isna(cell):
            return ""
    except (TypeError, ValueError):
        pass
    cell_str = str(cell)
    idx = cell_str.rfind("(")
    return cell_str[:idx].strip() if idx > 0 else cell_str.strip()


def _prompt_path_with_completion(prompt_text: str, default: Optional[str] = None) -> str:
    """
    Prompt for a filesystem path with basic tab completion support.
    Returns the entered string (may be empty).
    """
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


def _browse_for_file(
    title: str,
    default_dir: Optional[str],
    filetypes: Optional[Sequence[Tuple[str, str]]],
) -> str:
    """Open a GUI file picker if available; return the chosen path or empty string."""
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


def prompt_for_existing_file(
    label: str,
    *,
    default_dir: Optional[str] = None,
    filetypes: Optional[Sequence[Tuple[str, str]]] = None,
) -> str:
    """
    Prompt repeatedly until a valid file path is provided.
    Supports tab completion and optional GUI file picker by pressing Enter on an empty prompt.
    """
    prompt_text = f"{label} (Tab to autocomplete; Enter for picker): "
    while True:
        typed = _prompt_path_with_completion(prompt_text)
        if not typed:
            typed = _browse_for_file(label, default_dir, filetypes)
            if not typed:
                print("No file selected; please try again.")
                continue
        path = Path(os.path.expanduser(typed)).expanduser()
        if path.exists():
            return str(path)
        print(f"Path not found: {path}. Please try again.")


def resolve_csv_path(initial: Optional[str], label: str, default_dir: Optional[str]) -> Path:
    csv_types: Tuple[Tuple[str, str], ...] = (("CSV files", "*.csv"), ("All files", "*.*"))
    if initial:
        candidate = Path(initial).expanduser()
        if candidate.exists():
            return candidate
        print(f"{label} not found at {candidate}.")
    print(f"{label} not provided; please select a file.")
    chosen = prompt_for_existing_file(label, default_dir=default_dir, filetypes=csv_types)
    return Path(chosen).expanduser()


def load_lineups(lineup_csv: Path) -> Tuple[pd.DataFrame, List[str]]:
    df = pd.read_csv(lineup_csv)
    if df.empty:
        raise ValueError("Lineup pool CSV is empty.")
    roster_cols: List[str] = []
    for col in df.columns:
        if col is None:
            continue
        label = str(col).strip()
        if label.upper() in NON_ROSTER_LABELS:
            continue
        if label.startswith("Unnamed"):
            continue
        roster_cols.append(col)
    if len(roster_cols) < 7:
        raise ValueError("Could not infer roster columns; expected at least 7 roster slots.")
    return df, roster_cols


def build_player_text_map(lineups_df: pd.DataFrame, roster_cols: Sequence[str]) -> Dict[str, str]:
    text_map: Dict[str, str] = {}
    for _, row in lineups_df.iterrows():
        for col in roster_cols:
            pid = extract_player_id(row[col])
            if not pid:
                continue
            if pid not in text_map:
                text_map[pid] = extract_player_name(row[col])
    return text_map


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


def unique_players_in_df(lineups_df: pd.DataFrame, roster_cols: Sequence[str]) -> Set[str]:
    players: Set[str] = set()
    for _, row in lineups_df.iterrows():
        for col in roster_cols:
            pid = extract_player_id(row[col])
            if pid:
                players.add(pid)
    return players


def prune_lineups(
    lineups_df: pd.DataFrame,
    roster_cols: Sequence[str],
    usage_map: Dict[str, float],
    min_usage_frac: float
) -> Tuple[pd.DataFrame, Dict[str, int], Set[str]]:
    low_players = {pid for pid, val in usage_map.items() if val < min_usage_frac}
    before_n = len(lineups_df)
    players_before = len(unique_players_in_df(lineups_df, roster_cols))
    if not low_players:
        stats = {
            "n_before": before_n,
            "n_after": before_n,
            "removed_lineups": 0,
            "players_before": players_before,
            "players_after": players_before,
            "removed_players": 0,
        }
        return lineups_df, stats, low_players
    mask_df = lineups_df[roster_cols].applymap(extract_player_id)
    drop_mask = mask_df.isin(low_players).any(axis=1)
    pruned = lineups_df[~drop_mask].reset_index(drop=True)
    players_after = len(unique_players_in_df(pruned, roster_cols))
    stats = {
        "n_before": before_n,
        "n_after": len(pruned),
        "removed_lineups": int(drop_mask.sum()),
        "players_before": players_before,
        "players_after": players_after,
        "removed_players": players_before - players_after,
    }
    return pruned, stats, low_players


def load_projections(
    projections_csv: Path
) -> Tuple[pd.DataFrame, str, str, str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    df = pd.read_csv(projections_csv)
    if df.empty:
        raise ValueError("Projections CSV is empty.")
    id_col = next((c for c in ["Id", "ID", "PlayerId", "Player_ID", "PLAYER_ID", "player_id"] if c in df.columns), None)
    if not id_col:
        raise ValueError("Could not detect a player ID column in projections.")
    proj_col = next((c for c in ["FPPG", "Projection", "Proj", "PROJ", "Fantasy Points"] if c in df.columns), None)
    if not proj_col:
        raise ValueError("Could not detect a projection column in projections CSV.")
    pos_col = next((c for c in ["Position", "Pos", "POS"] if c in df.columns), None)
    if not pos_col:
        raise ValueError("Could not detect a position column in projections CSV.")
    team_col = next((c for c in ["Team", "TEAM", "team"] if c in df.columns), None)
    opp_col = next((c for c in ["Opponent", "Opp", "OPP"] if c in df.columns), None)
    game_col = next((c for c in ["Game", "Matchup", "MatchUp", "MATCHUP"] if c in df.columns), None)
    own_col = next((c for c in ["Projected Ownership", "Ownership", "OWN", "Own"] if c in df.columns), None)
    if "First Name" in df.columns and "Last Name" in df.columns:
        df["_FullName"] = df["First Name"].astype(str).str.strip() + " " + df["Last Name"].astype(str).str.strip()
        name_col: Optional[str] = "_FullName"
    else:
        name_col = next((c for c in ["Name", "Player", "PLAYER", "FullName", "Full Name"] if c in df.columns), None)
    return df, id_col, proj_col, pos_col, team_col, opp_col, name_col, game_col, own_col


def build_player_maps(
    proj_df: pd.DataFrame,
    id_col: str,
    proj_col: str,
    pos_col: str,
    team_col: Optional[str],
    opp_col: Optional[str],
    name_col: Optional[str],
    game_col: Optional[str],
    own_col: Optional[str]
) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, Optional[str]], Dict[str, Optional[str]],
           Dict[str, str], Dict[str, str], Dict[str, float]]:
    proj_map: Dict[str, float] = {}
    pos_map: Dict[str, str] = {}
    team_map: Dict[str, Optional[str]] = {}
    opp_map: Dict[str, Optional[str]] = {}
    name_map: Dict[str, str] = {}
    game_map: Dict[str, str] = {}
    ownership_map: Dict[str, float] = {}
    for _, row in proj_df.iterrows():
        pid_val = row[id_col]
        if pd.isna(pid_val):
            continue
        pid = str(pid_val).strip()
        if not pid:
            continue
        proj_val = row.get(proj_col, 0.0)
        proj_map[pid] = float(proj_val) if pd.notna(proj_val) else 0.0
        pos_val = row.get(pos_col, "")
        pos_map[pid] = str(pos_val).strip() if pd.notna(pos_val) else ""
        if team_col:
            team_val = row.get(team_col, None)
            team_map[pid] = str(team_val).strip() if pd.notna(team_val) else None
        else:
            team_map[pid] = None
        if opp_col:
            opp_val = row.get(opp_col, None)
            opp_map[pid] = str(opp_val).strip() if pd.notna(opp_val) else None
        else:
            opp_map[pid] = None
        if name_col:
            name_val = row.get(name_col, None)
            if pd.notna(name_val):
                name_map[pid] = str(name_val).strip()
        if game_col:
            game_val = row.get(game_col, None)
            if pd.notna(game_val):
                game_map[pid] = str(game_val).strip()
        if own_col:
            own_val = row.get(own_col, None)
            if pd.notna(own_val):
                ownership_map[pid] = float(own_val)
    return proj_map, pos_map, team_map, opp_map, name_map, game_map, ownership_map


@dataclass(frozen=True)
class Lineup:
    idx: int
    salary: int
    proj_sum: float
    pool_proj: float
    players_id: Tuple[str, ...]
    players_txt: Tuple[str, ...]
    corr_score: float
    max_stack: int
    pair_stacks: int
    triple_stacks: int
    cross_games: int
    goalie_support: int
    goalie_conflict: int
    uniq_logsum: float
    chalk_sum: float
    ownership_sum: float


def make_lineup_objects(
    lineups_df: pd.DataFrame,
    roster_cols: Sequence[str],
    proj_map: Dict[str, float],
    pos_map: Dict[str, str],
    team_map: Dict[str, Optional[str]],
    opp_map: Dict[str, Optional[str]],
    game_map: Dict[str, str],
    ownership_map: Dict[str, float],
    usage_map: Dict[str, float]
) -> List[Lineup]:
    objs: List[Lineup] = []
    for idx, row in lineups_df.iterrows():
        players_txt = [str(row[col]) for col in roster_cols]
        players_id = [extract_player_id(row[col]) for col in roster_cols]
        salary_val = row.get("Budget", row.get("Salary", 0))
        salary = int(salary_val) if pd.notna(salary_val) else 0
        proj_sum = sum(proj_map.get(pid, 0.0) for pid in players_id)
        pool_proj_val = row.get("FPPG", 0.0)
        pool_proj = float(pool_proj_val) if pd.notna(pool_proj_val) else 0.0
        if proj_sum <= 0.0 and pool_proj > 0.0:
            proj_sum = pool_proj
        skater_ids = [pid for pid in players_id if pos_map.get(pid, "").upper() != "G"]
        team_counts: Counter[str] = Counter(
            team_map.get(pid) for pid in skater_ids if team_map.get(pid)
        )
        stack_score = 0.0
        pair_count = 0
        triple_count = 0
        max_stack = max(team_counts.values()) if team_counts else 0
        for count in team_counts.values():
            if count >= 4:
                triple_count += 1
                stack_score += 1.6 + 0.25 * (count - 4)
            elif count == 3:
                triple_count += 1
                stack_score += 1.1
            elif count == 2:
                pair_count += 1
                stack_score += 0.45
        game_team_sets: Dict[str, Set[str]] = {}
        for pid in skater_ids:
            game = game_map.get(pid)
            team = team_map.get(pid)
            if not game or not team:
                continue
            game_team_sets.setdefault(game, set()).add(team)
        cross_games = sum(1 for teams in game_team_sets.values() if len(teams) >= 2)
        corr_score = stack_score + 0.35 * cross_games
        goalie_support = 0
        goalie_conflict = 0
        goalie_ids = [pid for pid in players_id if pos_map.get(pid, "").upper() == "G"]
        if goalie_ids:
            gid = goalie_ids[0]
            g_team = team_map.get(gid)
            g_opp = opp_map.get(gid)
            if g_team:
                goalie_support = sum(1 for pid in skater_ids if team_map.get(pid) == g_team)
                corr_score += 0.18 * goalie_support
            if g_opp:
                goalie_conflict = sum(1 for pid in skater_ids if team_map.get(pid) == g_opp)
                corr_score -= 0.65 * goalie_conflict
        uniq_logsum = 0.0
        chalk_sum = 0.0
        ownership_sum = 0.0
        for pid in players_id:
            usage = usage_map.get(pid, 1e-6)
            usage = max(usage, 1e-6)
            uniq_logsum += -math.log(usage)
            chalk_sum += usage
            ownership_sum += ownership_map.get(pid, 0.0)
        objs.append(Lineup(
            idx=idx,
            salary=salary,
            proj_sum=proj_sum,
            pool_proj=pool_proj,
            players_id=tuple(players_id),
            players_txt=tuple(players_txt),
            corr_score=corr_score,
            max_stack=max_stack,
            pair_stacks=pair_count,
            triple_stacks=triple_count,
            cross_games=cross_games,
            goalie_support=goalie_support,
            goalie_conflict=goalie_conflict,
            uniq_logsum=uniq_logsum,
            chalk_sum=chalk_sum,
            ownership_sum=ownership_sum,
        ))
    return objs


def normalize(values: Iterable[float]) -> List[float]:
    values_list = list(values)
    if not values_list:
        return []
    lo = min(values_list)
    hi = max(values_list)
    if hi <= lo + 1e-12:
        return [0.0 for _ in values_list]
    return [(val - lo) / (hi - lo) for val in values_list]


def overlap_count(player_set: Set[str], lineup_players: Tuple[str, ...]) -> int:
    return sum(1 for pid in lineup_players if pid in player_set)


def passes_caps(
    lineup: Lineup,
    selected: Sequence[Lineup],
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
    if max_repeat >= len(lineup.players_id):
        return True
    for chosen in selected:
        if overlap_count(set(chosen.players_id), lineup.players_id) > max_repeat:
            return False
    return True


def greedy_select(
    lineups: Sequence[Lineup],
    n_target: int,
    cap_pct: float,
    max_repeat_init: int,
    max_repeat_limit: int,
    selection_window: int,
    breadth_penalty: float,
    stalled_threshold: int,
    weights: Tuple[float, float, float, float],
    seed: Optional[int] = None,
) -> Tuple[List[Lineup], Dict[str, int], Dict[str, float]]:
    if seed is not None:
        random.seed(seed)
    cap_count = max(1, int(math.floor((cap_pct / 100.0) * n_target + 1e-9)))
    proj_norm = normalize([lu.proj_sum for lu in lineups])
    corr_norm = normalize([lu.corr_score for lu in lineups])
    uniq_norm = normalize([lu.uniq_logsum for lu in lineups])
    chalk_norm = normalize([lu.chalk_sum for lu in lineups])
    w_proj, w_corr, w_uniq, w_chalk = weights
    score_lookup: Dict[int, float] = {}
    rankings: List[Tuple[float, float, int]] = []
    for idx, lu in enumerate(lineups):
        base_score = (
            w_proj * proj_norm[idx]
            + w_corr * corr_norm[idx]
            + w_uniq * uniq_norm[idx]
            - w_chalk * chalk_norm[idx]
        )
        score_lookup[idx] = base_score
        rankings.append((base_score, random.random(), idx))
    rankings.sort(key=lambda x: (x[0], x[1]), reverse=True)
    order = [idx for _, _, idx in rankings]
    window = min(selection_window, len(order)) if selection_window > 0 else len(order)
    selected: List[Lineup] = []
    counts: Dict[str, int] = {}
    seen_sets: Set[frozenset] = set()
    max_repeat = max_repeat_init
    relaxations = 0
    pointer = 0
    stalled = 0
    while len(selected) < n_target and pointer < len(order):
        batch_indices = order[pointer:pointer + window]
        best_idx: Optional[int] = None
        best_score = float("-inf")
        for idx in batch_indices:
            lineup = lineups[idx]
            if not passes_caps(lineup, selected, counts, cap_count, max_repeat, seen_sets):
                continue
            penalty = 0.0
            for pid in lineup.players_id:
                filled = counts.get(pid, 0) / cap_count
                penalty += filled * filled
            final_score = score_lookup[idx] - breadth_penalty * penalty
            if final_score > best_score:
                best_score = final_score
                best_idx = idx
        if best_idx is not None:
            lineup = lineups[best_idx]
            selected.append(lineup)
            seen_sets.add(frozenset(lineup.players_id))
            for pid in lineup.players_id:
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
        "cap_count": cap_count,
        "cap_pct": cap_pct,
        "max_repeat_start": max_repeat_init,
        "max_repeat_final": max_repeat,
        "repeat_relaxations": relaxations,
        "picked": len(selected),
        "target": n_target,
        "lineups_considered": len(lineups),
        "total_proj": sum(l.proj_sum for l in selected),
        "window": window,
    }
    return selected, counts, diag


def export_selected_lineups(
    lineups_df: pd.DataFrame,
    roster_cols: Sequence[str],
    selected: Sequence[Lineup],
    output_csv: Path,
) -> None:
    if not selected:
        return
    indices = [lu.idx for lu in selected]
    subset = lineups_df.iloc[indices].copy().reset_index(drop=True)

    # Normalize roster columns to player IDs for FanDuel upload format
    for col in roster_cols:
        if col in subset.columns:
            subset[col] = subset[col].apply(extract_player_id)

    # Build headers that mimic the FanDuel template (duplicate slot labels)
    display_headers: List[str] = []
    for col in subset.columns:
        col_str = str(col)
        if "." in col_str and col_str.split(".", 1)[0].upper() not in NON_ROSTER_LABELS:
            display_headers.append(col_str.split(".", 1)[0])
        else:
            display_headers.append(col_str)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(display_headers)
        writer.writerows(subset.to_numpy())


def export_usage_report(
    counts: Dict[str, int],
    usage_map: Dict[str, float],
    name_map: Dict[str, str],
    text_map: Dict[str, str],
    pos_map: Dict[str, str],
    team_map: Dict[str, Optional[str]],
    proj_map: Dict[str, float],
    ownership_map: Dict[str, float],
    n_target: int,
    output_csv: Path,
) -> None:
    if not counts:
        return
    fieldnames = [
        "Player", "Player ID", "Position", "Team", "Selected Lineups", "Selected %",
        "Pool %", "Delta %", "Proj FPPG", "Proj Ownership"
    ]
    rows = []
    for pid, cnt in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        selected_pct = 100.0 * cnt / max(1, n_target)
        pool_pct = 100.0 * usage_map.get(pid, 0.0)
        delta = selected_pct - pool_pct
        proj = proj_map.get(pid, 0.0)
        own_val = ownership_map.get(pid)
        pos = pos_map.get(pid, "")
        team = team_map.get(pid) or ""
        player_name = name_map.get(pid) or text_map.get(pid) or pid
        rows.append({
            "Player": player_name,
            "Player ID": pid,
            "Position": pos,
            "Team": team,
            "Selected Lineups": cnt,
            "Selected %": f"{selected_pct:.1f}",
            "Pool %": f"{pool_pct:.1f}",
            "Delta %": f"{delta:+.1f}",
            "Proj FPPG": f"{proj:.2f}",
            "Proj Ownership": f"{own_val:.1f}" if own_val is not None else "",
        })
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pick an exposure-balanced FanDuel NHL lineup set.")
    parser.add_argument("lineup_csv", nargs="?", default=None, help="CSV of candidate lineups (FanDuel export).")
    parser.add_argument("projections_csv", nargs="?", default=None, help="Matched projections CSV for the slate.")
    parser.add_argument("--n", type=int, default=DEFAULT_N_TARGET, help="How many lineups to select (default 150).")
    parser.add_argument("--cap", type=float, default=DEFAULT_CAP_PCT, help="Max exposure per player in percent (default 40).")
    parser.add_argument("--max-repeat", type=int, default=DEFAULT_MAX_REPEAT_INIT, help="Initial max shared players between two chosen lineups.")
    parser.add_argument("--max-repeat-limit", type=int, default=DEFAULT_MAX_REPEAT_LIMIT, help="Upper bound for overlap relaxations.")
    parser.add_argument("--selection-window", type=int, default=DEFAULT_SELECTION_WINDOW, help="Top-N candidate window per greedy sweep.")
    parser.add_argument("--breadth-penalty", type=float, default=DEFAULT_BREADTH_PENALTY, help="Penalty factor for players nearing cap.")
    parser.add_argument("--stalled-threshold", type=int, default=DEFAULT_STALLED_THRESHOLD, help="Sweeps before relaxing overlap guard.")
    parser.add_argument("--min-usage-pct", type=float, default=DEFAULT_MIN_USAGE_PCT, help="Prune any lineup using a player below this pool pct.")
    parser.add_argument("--w-proj", type=float, default=DEFAULT_W_PROJ, help="Weight for projection score.")
    parser.add_argument("--w-corr", type=float, default=DEFAULT_W_CORR, help="Weight for correlation/stack score.")
    parser.add_argument("--w-uniq", type=float, default=DEFAULT_W_UNIQ, help="Weight for uniqueness (pool usage entropy).")
    parser.add_argument("--w-chalk", type=float, default=DEFAULT_W_CHALK, help="Penalty weight for chalkiness (pool usage sum).")
    parser.add_argument("--seed", type=int, help="Optional RNG seed for deterministic tie-breaking.")
    parser.add_argument("--out-prefix", help="Filename prefix for outputs (default: derived from lineup CSV).")
    parser.add_argument("--out-dir", default="autoNHL", help="Directory for outputs (default: autoNHL).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lineup_path = resolve_csv_path(args.lineup_csv, "Lineup CSV", "lineups")
    proj_path = resolve_csv_path(args.projections_csv, "Projections CSV", "projections-csv")
    print(f"Loading lineup pool from {lineup_path}…")
    print(f"Loading projections from {proj_path}…")

    lineups_df, roster_cols = load_lineups(lineup_path)
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

    text_map = build_player_text_map(lineups_df, roster_cols)
    print("Building projection + metadata maps…")
    proj_df, id_col, proj_col, pos_col, team_col, opp_col, name_col, game_col, own_col = load_projections(proj_path)
    proj_map, pos_map, team_map, opp_map, name_map, game_map, ownership_map = build_player_maps(
        proj_df, id_col, proj_col, pos_col, team_col, opp_col, name_col, game_col, own_col
    )
    print("Constructing lineup objects for scoring…")
    lineup_objects = make_lineup_objects(
        lineups_df, roster_cols, proj_map, pos_map, team_map, opp_map, game_map, ownership_map, usage_map
    )
    if not lineup_objects:
        raise ValueError("Failed to build lineup objects from the pool.")

    weights = (args.w_proj, args.w_corr, args.w_uniq, args.w_chalk)
    print("Running greedy lineup selection…")
    selected, counts, diag = greedy_select(
        lineup_objects,
        n_target=args.n,
        cap_pct=args.cap,
        max_repeat_init=args.max_repeat,
        max_repeat_limit=args.max_repeat_limit,
        selection_window=args.selection_window,
        breadth_penalty=args.breadth_penalty,
        stalled_threshold=args.stalled_threshold,
        weights=weights,
        seed=args.seed,
    )
    if not selected:
        raise RuntimeError("Selector could not find any lineups under the given constraints.")
    print(f"Selected {len(selected)} lineups (target {args.n}).")

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.out_prefix or f"fdnhl_{lineup_path.stem}"
    selected_path = out_dir / f"{prefix}_selected_lineups.csv"
    usage_path = out_dir / f"{prefix}_usage_report.csv"
    summary_path = out_dir / f"{prefix}_summary.txt"

    print(f"Writing selected lineups to {selected_path}…")
    export_selected_lineups(lineups_df, roster_cols, selected, selected_path)
    print(f"Writing usage report to {usage_path}…")
    export_usage_report(
        counts=counts,
        usage_map=usage_map,
        name_map=name_map,
        text_map=text_map,
        pos_map=pos_map,
        team_map=team_map,
        proj_map=proj_map,
        ownership_map=ownership_map,
        n_target=args.n,
        output_csv=usage_path,
    )

    summary_lines: List[str] = []
    summary_lines.append(f"NHL picker selected {len(selected)}/{args.n} lineups (pool before={pool_before}, after={len(lineups_df)}).")
    if prune_stats and prune_stats.get("removed_lineups", 0):
        summary_lines.append(
            f"Pruned {prune_stats['removed_lineups']} lineups ({len(low_players)} low-usage players < {args.min_usage_pct:.2f}%)."
        )
    summary_lines.append(
        f"Exposure cap {diag['cap_pct']:.1f}% → {diag['cap_count']} lineups, overlap {diag['max_repeat_start']} → {diag['max_repeat_final']} (relaxed {diag['repeat_relaxations']}x)."
    )
    if diag["picked"] < args.n:
        summary_lines.append("WARNING: Could not fill the full target under current caps/overlap settings.")

    if selected:
        proj_values = [lu.proj_sum for lu in selected]
        summary_lines.append(
            f"Projection avg {statistics.mean(proj_values):.2f}, median {statistics.median(proj_values):.2f}, range {min(proj_values):.2f}-{max(proj_values):.2f}."
        )
        corr_mean = statistics.mean(lu.corr_score for lu in selected)
        summary_lines.append(f"Average correlation score {corr_mean:.3f} (weights: proj={weights[0]:.2f}, corr={weights[1]:.2f}, uniq={weights[2]:.2f}, chalk={weights[3]:.2f}).")
        stack_counter = Counter(lu.max_stack for lu in selected)
        stack_summary = ", ".join(f"{size}-man:{count}" for size, count in sorted(stack_counter.items(), reverse=True))
        summary_lines.append(f"Max stack sizes seen: {stack_summary or 'n/a'}.")
        goalie_conflict_total = sum(lu.goalie_conflict for lu in selected)
        goalie_conflict_lineups = sum(1 for lu in selected if lu.goalie_conflict > 0)
        summary_lines.append(f"Goalie conflicts: {goalie_conflict_total} skaters across {goalie_conflict_lineups} lineups.")
        cross_game_total = sum(lu.cross_games for lu in selected)
        summary_lines.append(f"Cross-game mini-stacks: {cross_game_total} total instances.")
        players_at_cap = [pid for pid, cnt in counts.items() if cnt >= diag["cap_count"]]
        if players_at_cap:
            summary_lines.append(f"Players at cap ({len(players_at_cap)}): " + ", ".join(players_at_cap))

        summary_lines.append("Top exposures (selected% | pool% | Δ | POS | TEAM | player [id] | proj | own):")
        top_exposures = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:12]
        for pid, cnt in top_exposures:
            selected_pct = 100.0 * cnt / max(1, args.n)
            pool_pct = 100.0 * usage_map.get(pid, 0.0)
            delta = selected_pct - pool_pct
            proj_val = proj_map.get(pid, 0.0)
            own_val = ownership_map.get(pid)
            pos = pos_map.get(pid, "")
            team = team_map.get(pid) or ""
            name = name_map.get(pid) or text_map.get(pid) or pid
            line = f"  {selected_pct:5.1f}% | {pool_pct:5.1f}% | {delta:+5.1f} | {pos:<3} | {team:<3} | {name} [{pid}] | {proj_val:5.2f}"
            if own_val is not None:
                line += f" | {own_val:4.1f}%"
            summary_lines.append(line)

    summary_lines.append("Outputs:")
    summary_lines.append(f"  Selected lineups → {selected_path}")
    summary_lines.append(f"  Usage report     → {usage_path}")
    summary_lines.append(f"  Summary          → {summary_path}")

    summary_text = "\n".join(summary_lines)
    print(f"Writing summary to {summary_path}…")
    summary_path.write_text(summary_text)
    print(summary_text)


if __name__ == "__main__":
    main()
