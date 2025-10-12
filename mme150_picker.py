#!/usr/bin/env python3
"""
MME 150 Lineup Auto-Selector (FanDuel NFL) — with pruning + usage report + summary
-----------------------------------------------------------------------------------
- Prompts for: lineup pool CSV (~50k), projections CSV, FanDuel upload template CSV
- Auto-prunes lineups that include any player under a pool-usage cutoff (default 2%)
- Picks 150 lineups preferring high projection, uniqueness, stack bonuses, and breadth
- Outputs to ./autoMME by default:
    - <prefix>_fanduel_upload.csv   (columns follow your FD template)
    - <prefix>_usage_report.csv     (player name, 150-exposure, pool-exposure, delta)
    - <prefix>_summary.txt          (totals, exposure max, stack distribution, prune stats)

Run:
    python mme150_picker.py [--cap 25] [--repeat 4] [--min-usage-pct 2] [--out-prefix week6] [--out-dir autoMME]
"""

import re, math, sys, argparse, random, csv
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Set
from pathlib import Path
from datetime import datetime  # add near the top
import pandas as pd


# ------------------- Roster + parsing helpers -------------------

ROSTER_COLS = ["QB","RB","RB.1","WR","WR.1","WR.2","TE","FLEX","DEF"]
ID_REGEX = re.compile(r"\(([^)]+)\)\s*$")  # Name(PLAYERID) → capture PLAYERID

def extract_player_id(cell: str) -> str:
    if not isinstance(cell, str): return ""
    m = ID_REGEX.search(cell)
    return m.group(1) if m else cell.strip()

def extract_player_name(cell: str) -> str:
    if not isinstance(cell, str): return ""
    i = cell.rfind('(')
    return cell[:i].strip() if i > 0 else cell.strip()

# ------------------- File picker -------------------

def pick_file_cli_or_gui(title: str) -> str:
    """Try Tk file picker; if unavailable, fall back to stdin path."""
    try:
        import tkinter as tk
        from tkinter.filedialog import askopenfilename
        root = tk.Tk(); root.withdraw()
        fp = askopenfilename(title=title, filetypes=[("CSV files","*.csv"), ("All files","*.*")])
        root.update(); root.destroy()
        if fp: return fp
    except Exception:
        pass
    return input(f"{title} (path): ").strip()

# ------------------- Projections detection -------------------

def detect_columns(df: pd.DataFrame) -> Tuple[str, str, str, Optional[str], Optional[str]]:
    """Return (id_col, proj_col, pos_col, team_col?, name_col?)."""
    # ID
    id_col = None
    for c in ["B_Id","Id","PlayerId","Player_ID","PLAYER_ID","id"]:
        if c in df.columns: id_col = c; break
    if id_col is None:
        cands = [c for c in df.columns if "id" in c.lower()]
        id_col = min(cands, key=len) if cands else df.columns[0]
    # Projection
    proj_col = "A_ppg_projection" if "A_ppg_projection" in df.columns else None
    if proj_col is None:
        for c in df.columns:
            cl = c.lower()
            if "proj" in cl or cl in ("fppg","points","projection","ppg"):
                proj_col = c; break
    if proj_col is None:
        raise ValueError("Could not detect projection column in projections CSV.")
    # Position
    pos_col = None
    for c in ["B_Position","Position","POS","Pos"]:
        if c in df.columns: pos_col = c; break
    if pos_col is None:
        cands = [c for c in df.columns if "pos" in c.lower() or "position" in c.lower()]
        pos_col = cands[0] if cands else None
    if pos_col is None:
        raise ValueError("Could not detect position column in projections CSV.")
    # Team (optional)
    team_col = None
    for c in ["B_Team","Team","TEAM","Tm","team"]:
        if c in df.columns: team_col = c; break
    if team_col is None:
        cands = [c for c in df.columns if "team" in c.lower() and "opp" not in c.lower()]
        team_col = cands[0] if cands else None
    # Name (optional)
    name_col = None
    for c in ["B_Nickname","Nickname","Player","Name","PLAYER","PLAYER_NAME","FullName"]:
        if c in df.columns: name_col = c; break
    return id_col, proj_col, pos_col, team_col, name_col

def load_projections(proj_csv: str) -> Tuple[pd.DataFrame, str, str, str, Optional[str], Optional[str]]:
    df = pd.read_csv(proj_csv)
    id_col, proj_col, pos_col, team_col, name_col = detect_columns(df)
    # Opponent (optional)
    opp_col = None
    for c in ["B_Opponent","Opponent","Opp","OPP","opp"]:
        if c in df.columns: opp_col = c; break
    if opp_col is None:
        cands = [c for c in df.columns if "opp" in c.lower()]
        opp_col = cands[0] if cands else None
    # Rename to standardized columns
    ren = {id_col:"B_Id", proj_col:"A_ppg_projection", pos_col:"B_Position"}
    if team_col: ren[team_col] = "B_Team"
    if opp_col:  ren[opp_col]  = "B_Opponent"
    if name_col: ren[name_col] = "B_Name"
    std = df.rename(columns=ren)
    keep = ["B_Id","A_ppg_projection","B_Position"]
    if "B_Team" in std.columns: keep.append("B_Team")
    if "B_Opponent" in std.columns: keep.append("B_Opponent")
    if "B_Name" in std.columns: keep.append("B_Name")
    std = std[keep].copy()
    return std, "B_Id", "A_ppg_projection", "B_Position", ("B_Team" if "B_Team" in std.columns else None), ("B_Name" if "B_Name" in std.columns else None)

def load_lineups(lineups_csv: str) -> pd.DataFrame:
    df = pd.read_csv(lineups_csv)
    for col in ROSTER_COLS:
        if col not in df.columns:
            raise ValueError(f"Lineups CSV missing required column: {col}")
    return df

def build_player_maps(proj_df: pd.DataFrame):
    proj_map, pos_map, team_map, opp_map, name_map = {}, {}, {}, {}, {}
    has_team = "B_Team" in proj_df.columns
    has_opp  = "B_Opponent" in proj_df.columns
    has_name = "B_Name" in proj_df.columns
    for _, r in proj_df.iterrows():
        pid = str(r["B_Id"])
        proj_map[pid] = float(r["A_ppg_projection"]) if pd.notna(r["A_ppg_projection"]) else 0.0
        pos_map[pid]  = str(r["B_Position"]) if pd.notna(r["B_Position"]) else ""
        team_map[pid] = (str(r["B_Team"]) if pd.notna(r.get("B_Team", None)) else None) if has_team else None
        opp_map[pid]  = (str(r["B_Opponent"]) if pd.notna(r.get("B_Opponent", None)) else None) if has_opp else None
        name_map[pid] = (str(r["B_Name"]) if pd.notna(r.get("B_Name", None)) else None) if has_name else None
    return proj_map, pos_map, team_map, opp_map, name_map

# ------------------- Pool usage + pruning -------------------

def compute_pool_usage(lineups_df: pd.DataFrame) -> Dict[str, float]:
    from collections import Counter
    cnt = Counter()
    total = len(lineups_df)
    for _, r in lineups_df.iterrows():
        for col in ROSTER_COLS:
            pid = extract_player_id(r[col])
            if pid: cnt[pid] += 1
    return {pid: c / total for pid, c in cnt.items()}

def unique_players_in_df(lineups_df: pd.DataFrame) -> Set[str]:
    s: Set[str] = set()
    for _, r in lineups_df.iterrows():
        for col in ROSTER_COLS:
            s.add(extract_player_id(r[col]))
    return s

def prune_by_min_usage(lineups_df: pd.DataFrame, min_usage_frac: float):
    """
    Drop any lineup that contains a player whose pool usage < min_usage_frac.
    Returns: pruned_df, stats_dict, low_players_set
    """
    usage_full = compute_pool_usage(lineups_df)
    low_players = {pid for pid, u in usage_full.items() if u < min_usage_frac}
    if not low_players:
        stats = {
            "n_before": len(lineups_df),
            "n_after": len(lineups_df),
            "removed_lineups": 0,
            "players_before": len(unique_players_in_df(lineups_df)),
            "players_after": len(unique_players_in_df(lineups_df)),
            "removed_players": 0,
        }
        return lineups_df, stats, low_players
    # fast vectorized mask: reject rows where any roster slot is a low-usage player
    bad_mask = lineups_df[ROSTER_COLS].applymap(extract_player_id).isin(low_players).any(axis=1)
    pruned = lineups_df[~bad_mask].reset_index(drop=True)
    stats = {
        "n_before": len(lineups_df),
        "n_after": len(pruned),
        "removed_lineups": int(bad_mask.sum()),
        "players_before": len(unique_players_in_df(lineups_df)),
        "players_after": len(unique_players_in_df(pruned)),
        "removed_players": len(unique_players_in_df(lineups_df)) - len(unique_players_in_df(pruned)),
    }
    return pruned, stats, low_players

# ------------------- Lineup object + selection -------------------

@dataclass(frozen=True)
class Lineup:
    idx: int
    salary: int
    players_id: Tuple[str, ...]
    players_txt: Tuple[str, ...]
    proj_sum: float
    qb_team: Optional[str]
    qb_opp: Optional[str]
    wr_te_on_qb_team: int
    bringbacks: int
    uniq_logsum: float
    chalk_sum: float

def make_lineup_objects(lineups_df: pd.DataFrame, proj_map: Dict[str,float],
                        team_map: Dict[str,Optional[str]], opp_map: Dict[str,Optional[str]],
                        pos_map: Dict[str,str], usage: Dict[str,float]) -> List[Lineup]:
    objs: List[Lineup] = []
    for idx, r in lineups_df.iterrows():
        players_txt = [str(r[c]) for c in ROSTER_COLS]
        players_id  = [extract_player_id(str(r[c])) for c in ROSTER_COLS]
        salary = int(r["Budget"]) if "Budget" in r and pd.notna(r["Budget"]) else 0
        # projection sum
        proj_sum = sum(proj_map.get(pid, 0.0) for pid in players_id)
        # QB stack + bring-back
        qb_id = players_id[0]
        qb_team = team_map.get(qb_id, None)
        qb_opp  = opp_map.get(qb_id, None)
        wr_te_on = 0; bringbacks = 0
        if qb_team is not None:
            for pid in players_id[1:]:
                if pos_map.get(pid, "") in ("WR","TE","RB") and team_map.get(pid, None) == qb_team:
                    wr_te_on += 1
        if qb_team is not None and qb_opp is not None:
            for pid in players_id[1:]:
                if team_map.get(pid, None) == qb_opp:
                    bringbacks += 1
        # uniqueness & chalk
        uq = 0.0; ch = 0.0
        for pid in players_id:
            u = usage.get(pid, 1e-9)
            uq += -math.log(max(1e-9, u))
            ch += u
        objs.append(Lineup(idx, salary, tuple(players_id), tuple(players_txt), proj_sum,
                           qb_team, qb_opp, wr_te_on, bringbacks, uq, ch))
    return objs

def normalize(values: List[float]) -> List[float]:
    lo = min(values); hi = max(values)
    if hi <= lo + 1e-12: return [0.0]*len(values)
    return [(v - lo) / (hi - lo) for v in values]

def overlap_count(a: Set[str], b: Tuple[str, ...]) -> int:
    return sum(1 for x in b if x in a)

def passes_caps(lu: Lineup, selected: List[Lineup], counts: Dict[str,int],
                cap_count: int, max_repeat: int, seen_sets: Set[frozenset]) -> bool:
    for pid in lu.players_id:
        if counts.get(pid, 0) + 1 > cap_count: return False
    lu_set = set(lu.players_id)
    for ch in selected:
        if overlap_count(lu_set, ch.players_id) > max_repeat: return False
    if frozenset(lu.players_id) in seen_sets: return False
    return True

def greedy_select(lineups: List[Lineup], n_target: int = 150,
                  cap_pct: float = 20.0, max_repeat_init: int = 4,
                  w_proj: float = 0.55, w_stack: float = 0.15,
                  w_uniq: float = 0.30, w_chalk: float = 0.05,
                  qb2_bonus: float = 1.0, bring_bonus: float = 0.6,
                  seed: Optional[int] = 42):
    if seed is not None: random.seed(seed)
    cap_count = int(math.floor((cap_pct/100.0) * n_target + 1e-9))  # e.g., 37 for 150 @ 25%
    proj_list = [lu.proj_sum for lu in lineups]
    uniq_list = [lu.uniq_logsum for lu in lineups]
    chalk_list = [lu.chalk_sum for lu in lineups]
    proj_norm = normalize(proj_list); uniq_norm = normalize(uniq_list); chalk_norm = normalize(chalk_list)

    def stack_score(lu: Lineup) -> float:
        return (qb2_bonus if lu.wr_te_on_qb_team >= 2 else 0.0) + (bring_bonus if lu.bringbacks >= 1 else 0.0)

    base_scores = []
    for i, lu in enumerate(lineups):
        s = (w_proj * proj_norm[i] + w_stack * stack_score(lu) + w_uniq * uniq_norm[i] - w_chalk * chalk_norm[i])
        base_scores.append((s, i))
    base_scores.sort(key=lambda x: x[0], reverse=True)
    order = [i for _, i in base_scores]

    selected: List[Lineup] = []
    counts: Dict[str,int] = {}
    seen_sets: Set[frozenset] = set()
    max_repeat = max_repeat_init
    window = 5000 if len(lineups) > 6000 else len(lineups)

    relaxations = 0; ptr = 0; stalled = 0
    while len(selected) < n_target and ptr < len(order):
        batch = order[ptr:ptr+window]
        best_i = None; best_score = -1e18
        for i in batch:
            lu = lineups[i]
            if not passes_caps(lu, selected, counts, cap_count, max_repeat, seen_sets): continue
            # dynamic breadth penalty for near-cap players
            pen = 0.0
            for pid in lu.players_id:
                u = counts.get(pid, 0) / max(1, cap_count)
                pen += u*u
            score = base_scores[i][0] - 0.05*pen
            if score > best_score: best_score = score; best_i = i
        if best_i is not None:
            lu = lineups[best_i]
            selected.append(lu)
            seen_sets.add(frozenset(lu.players_id))
            for pid in lu.players_id: counts[pid] = counts.get(pid, 0) + 1
            stalled = 0
        else:
            stalled += 1
            if stalled >= 3 and max_repeat < 6:
                max_repeat += 1; relaxations += 1; stalled = 0
            else:
                ptr += window

    diag = {
        "cap_count": cap_count,
        "max_repeat_start": max_repeat_init,
        "max_repeat_final": max_repeat,
        "repeat_relaxations": relaxations,
        "picked": len(selected),
        "total_proj": sum(l.proj_sum for l in selected),
        "qb2_count": sum(1 for l in selected if l.wr_te_on_qb_team >= 2),
        "bringback_count": sum(1 for l in selected if l.bringbacks >= 1),
        "both_qb2_and_bring": sum(1 for l in selected if l.wr_te_on_qb_team >= 2 and l.bringbacks >= 1),
    }
    return selected, counts, diag

# ------------------- Exports -------------------


def export_fanduel(template_csv: str, selected: List[Lineup], out_csv: str):
    """
    Write selected lineups using the exact header order from the FanDuel template.
    - Preserves duplicate headers (RB, RB, WR, WR, WR) by writing with csv module.
    - Exports **ID only** (no "Name(id)" text) to satisfy FD parser.
    - Supports defense column named "D", "DEF", or "DST".
    """
    # Read headers exactly as in the template (preserve duplicates)
    with open(template_csv, "r", newline="") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError("FanDuel template appears empty.")

    # Normalized label helper
    def norm(lbl: str) -> str:
        return (lbl or "").strip().upper()

    # Prepare output rows for each selected lineup
    rows = []
    for lu in selected:
        # slot indices in our lineup object (ROSTER_COLS order)
        # QB=0, RB=1, RB.1=2, WR=3, WR.1=4, WR.2=5, TE=6, FLEX=7, DEF=8
        rb_i = wr_i = 0  # which RB/WR occurrence we are filling
        row = [""] * len(headers)
        for j, h in enumerate(headers):
            hN = norm(h)
            if hN == "QB":
                row[j] = lu.players_id[0]
            elif hN == "RB":
                # first RB -> index 1, second RB -> index 2
                if rb_i == 0:
                    row[j] = lu.players_id[1]
                elif rb_i == 1:
                    row[j] = lu.players_id[2]
                rb_i += 1
            elif hN == "WR":
                # WR occurrences map to indices 3,4,5
                if wr_i == 0:
                    row[j] = lu.players_id[3]
                elif wr_i == 1:
                    row[j] = lu.players_id[4]
                elif wr_i == 2:
                    row[j] = lu.players_id[5]
                wr_i += 1
            elif hN == "TE":
                row[j] = lu.players_id[6]
            elif hN == "FLEX":
                row[j] = lu.players_id[7]
            elif hN in ("D", "DEF", "DST"):
                row[j] = lu.players_id[8]
            else:
                # Non-roster column in template (e.g., "Instructions") --> leave blank
                row[j] = ""
        rows.append(row)

    # Write CSV with exact headers
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def export_usage_report(selected: List[Lineup], full_usage: Dict[str,float], out_csv: str,
                        name_map: Dict[str, Optional[str]], fallback_names: Dict[str, str]):
    from collections import Counter
    sel_cnt = Counter()
    for lu in selected:
        for pid in lu.players_id: sel_cnt[pid] += 1
    n_sel = len(selected)
    recs = []
    for pid, sel_n in sel_cnt.items():
        sel_pct = sel_n / max(1, n_sel)
        pool_pct = full_usage.get(pid, 0.0)
        name = name_map.get(pid) or fallback_names.get(pid) or ""
        recs.append({"player_id": pid, "player_name": name, "selected_count": sel_n,
                     "selected_pct": sel_pct, "pool_pct": pool_pct, "delta_pct": sel_pct - pool_pct})
    pd.DataFrame(recs).sort_values("selected_pct", ascending=False).to_csv(out_csv, index=False)

def write_summary(out_path: str, diagnostics: dict, counts: Dict[str,int], n_target: int, prune_stats: Optional[dict] = None):
    max_exp_ct = max(counts.values()) if counts else 0
    max_exp_pct = (max_exp_ct / max(1, n_target)) * 100.0
    with open(out_path, "w") as f:
        f.write("MME 150 Selection Summary\n")
        f.write("=========================\n")
        f.write(f"Picked: {diagnostics.get('picked', 0)}\n")
        f.write(f"Total Projection: {diagnostics.get('total_proj', 0.0):.2f}\n")
        f.write(f"Per-player Cap (count): {diagnostics.get('cap_count')}\n")
        f.write(f"Max Exposure Used: {max_exp_ct} ({max_exp_pct:.1f}%)\n")
        f.write(f"Max Repeat: start {diagnostics.get('max_repeat_start')} -> final {diagnostics.get('max_repeat_final')}\n")
        f.write(f"Repeat Relaxations: {diagnostics.get('repeat_relaxations')}\n")
        if prune_stats:
            f.write("\nPrune Settings/Stats\n")
            f.write("---------------------\n")
            f.write(f"  Min usage cutoff: {prune_stats.get('min_usage_pct', 0):.2f}%\n")
            f.write(f"  Lineups: {prune_stats.get('n_before',0)} → {prune_stats.get('n_after',0)} (removed {prune_stats.get('removed_lineups',0)})\n")
            f.write(f"  Players: {prune_stats.get('players_before',0)} → {prune_stats.get('players_after',0)} (removed {prune_stats.get('removed_players',0)})\n")
        f.write("\nStack Distribution (out of selected):\n")
        f.write(f"  QB+2: {diagnostics.get('qb2_count', 0)}\n")
        f.write(f"  Bring-back ≥1: {diagnostics.get('bringback_count', 0)}\n")
        f.write(f"  Both (QB+2 & Bring-back): {diagnostics.get('both_qb2_and_bring', 0)}\n")

# ------------------- main -------------------

def main():
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
    ap = argparse.ArgumentParser()
    ap.add_argument("--lineups", type=str, help="Path to lineup pool CSV")
    ap.add_argument("--projections", type=str, help="Path to projections CSV")
    ap.add_argument("--template", type=str, help="Path to FanDuel template CSV")
    ap.add_argument("--out-prefix", type=str, default=f"mme150-{ts}")
    ap.add_argument("--out-dir", type=str, default="autoMME", help="Output folder (default: autoMME)")
    ap.add_argument("--cap", type=float, default=20.0, help="Max exposure percent per player (default 25)")
    ap.add_argument("--repeat", type=int, default=4, help="Max repeating players between any two selected (start)")
    ap.add_argument("--min-usage-pct", type=float, default=2.0, help="Prune lineups containing players under this pool-usage percentage (default 2.0)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    lineups_csv = args.lineups or pick_file_cli_or_gui("Select LINEUPS CSV")
    proj_csv    = args.projections or pick_file_cli_or_gui("Select PROJECTIONS CSV")
    templ_csv   = args.template or pick_file_cli_or_gui("Select FanDuel TEMPLATE CSV")

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading...")
    ldf = load_lineups(lineups_csv)
    pdf, idcol, projcol, poscol, teamcol, namecol = load_projections(proj_csv)

    print("Building maps...")
    proj_map, pos_map, team_map, opp_map, name_map = build_player_maps(pdf)

    min_usage_frac = max(0.0, float(args.min_usage_pct) / 100.0)
    print(f"Pruning lineups with players under {args.min_usage_pct:.2f}% pool usage...")
    ldf_pruned, prune_stats_raw, low_players = prune_by_min_usage(ldf, min_usage_frac)
    prune_stats = dict(prune_stats_raw)
    prune_stats["min_usage_pct"] = args.min_usage_pct
    print(f"  Lineups: {prune_stats_raw['n_before']} → {prune_stats_raw['n_after']} (removed {prune_stats_raw['removed_lineups']})")
    print(f"  Players: {prune_stats_raw['players_before']} → {prune_stats_raw['players_after']} (removed {prune_stats_raw['removed_players']})")

    print("Computing pool usage (post-prune baseline)...")
    usage = compute_pool_usage(ldf_pruned)

    print("Making lineup objects...")
    lineup_objs = make_lineup_objects(ldf_pruned, proj_map, team_map, opp_map, pos_map, usage)

    print(f"Selecting 150 (cap={args.cap}%, repeat_start={args.repeat})...")
    selected, counts, diagnostics = greedy_select(lineup_objs, n_target=150, cap_pct=args.cap, max_repeat_init=args.repeat, seed=args.seed)

    # build fallback names for usage report
    fallback_names: Dict[str,str] = {}
    for lu in selected:
        for cell_txt, pid in zip(lu.players_txt, lu.players_id):
            if not name_map.get(pid):
                nm = extract_player_name(cell_txt)
                if nm: fallback_names[pid] = nm

    out_prefix = Path(args.out_prefix).stem
    out_upload = out_dir / f"{out_prefix}_fanduel_upload.csv"
    out_usage  = out_dir / f"{out_prefix}_usage_report.csv"
    out_summary= out_dir / f"{out_prefix}_summary.txt"

    print(f"Writing FanDuel upload CSV -> {out_upload}")
    export_fanduel(templ_csv, selected, str(out_upload))

    print(f"Writing Usage report -> {out_usage}")
    export_usage_report(selected, usage, str(out_usage), name_map, fallback_names)

    print(f"Writing Summary -> {out_summary}")
    write_summary(str(out_summary), diagnostics, counts, n_target=150, prune_stats=prune_stats)

    total_proj = diagnostics.get("total_proj", 0.0)
    max_exp_ct = max(counts.values()) if counts else 0
    max_exp_pct = (max_exp_ct / max(1, len(selected))) * 100.0
    print(f"Done. Picked {len(selected)} lineups | Total proj={total_proj:.2f} | Max exposure count={max_exp_ct} ({max_exp_pct:.1f}%)")
    print("Files written:")
    print(f" - {out_upload}")
    print(f" - {out_usage}")
    print(f" - {out_summary}")

if __name__ == "__main__":
    main()
