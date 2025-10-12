#!/usr/bin/env python3
"""
MME 150 Lineup Auto-Selector (FanDuel NFL)
------------------------------------------
- Input: lineup pool CSV (50k), projections CSV, FanDuel upload template CSV
- Output: FanDuel-formatted upload CSV for the selected 150 lineups,
          a player usage report (selected vs full pool),
          and a summary.txt with totals + stack distribution + any cap relaxations.

Assumptions for v1 (based on your files):
- Lineups CSV columns include: QB, RB, RB.1, WR, WR.1, WR.2, TE, FLEX, DEF, Budget, FPPG
  Each cell looks like 'Name(121339-XXXXX)'. We extract the id in parentheses.
- Projections CSV columns include (at least): B_Id, B_Position, A_ppg_projection, B_Opponent
  If a team column exists (e.g., B_Team), we'll use it; otherwise stack bonuses will be minimal.
- FanDuel template CSV provides the roster column order to write (QB, RB, RB.1, WR, WR.1, WR.2, TE, FLEX, DEF, ...).

Run:
  python mme150_picker.py
It will prompt for the three files via a file picker (Tk), or fallback to CLI paths.
"""

import re
import math
import sys
import argparse
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from pathlib import Path

import pandas as pd

# ------------------- File pickers -------------------

def pick_file_cli_or_gui(title: str) -> str:
    """Try a Tk file picker. If it fails (e.g., headless), fallback to input()."""
    try:
        import tkinter as tk
        from tkinter.filedialog import askopenfilename
        root = tk.Tk()
        root.withdraw()
        fp = askopenfilename(title=title, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        root.update()
        root.destroy()
        if fp:
            return fp
    except Exception:
        pass
    # CLI fallback
    return input(f"{title} (path): ").strip()


# ------------------- Helpers -------------------

ID_REGEX = re.compile(r"\(([^)]+)\)\s*$")  # capture text inside last parentheses

ROSTER_COLS = ["QB","RB","RB.1","WR","WR.1","WR.2","TE","FLEX","DEF"]

def extract_player_id(cell: str) -> str:
    if not isinstance(cell, str):
        return ""
    m = ID_REGEX.search(cell)
    return m.group(1) if m else cell.strip()


def extract_player_name(cell: str) -> str:
    """Best-effort: name part before '(id)'."""
    if not isinstance(cell, str):
        return ""
    i = cell.rfind('(')
    return cell[:i].strip() if i > 0 else cell.strip()


def detect_columns(df: pd.DataFrame) -> Tuple[str, str, str, Optional[str], Optional[str]]:
    """
    For projections: return (id_col, proj_col, pos_col, team_col_opt, name_col_opt)
    Prefers known names, falls back to heuristics.
    """
    # ID
    id_col = None
    for c in ["B_Id","Id","PlayerId","Player_ID","PLAYER_ID","id"]:
        if c in df.columns:
            id_col = c
            break
    if id_col is None:
        candidates = [c for c in df.columns if "id" in c.lower()]
        id_col = min(candidates, key=len) if candidates else df.columns[0]

    # Projection
    proj_col = "A_ppg_projection" if "A_ppg_projection" in df.columns else None
    if proj_col is None:
        for c in df.columns:
            cl = c.lower()
            if "proj" in cl or cl in ("fppg","points","projection","ppg"):
                proj_col = c
                break
    if proj_col is None:
        raise ValueError("Could not detect projection column in projections CSV.")

    # Position
    pos_col = None
    for c in ["B_Position","Position","POS","Pos"]:
        if c in df.columns:
            pos_col = c
            break
    if pos_col is None:
        candidates = [c for c in df.columns if "pos" in c.lower() or "position" in c.lower()]
        pos_col = candidates[0] if candidates else None
    if pos_col is None:
        raise ValueError("Could not detect position column in projections CSV.")

    # Team (optional)
    team_col = None
    for c in ["B_Team","Team","TEAM","Tm","team"]:
        if c in df.columns:
            team_col = c
            break
    if team_col is None:
        candidates = [c for c in df.columns if "team" in c.lower() and "opp" not in c.lower()]
        team_col = candidates[0] if candidates else None

    # Name (optional)
    name_col = None
    for c in ["B_Nickname","Nickname","Player","Name","PLAYER","PLAYER_NAME","FullName"]:
        if c in df.columns:
            name_col = c
            break

    return id_col, proj_col, pos_col, team_col, name_col


@dataclass(frozen=True)
class Lineup:
    idx: int
    salary: int
    players_id: Tuple[str, ...]     # tuple of player ids (length 9)
    players_txt: Tuple[str, ...]    # tuple of "Name(id)" strings for export
    proj_sum: float
    qb_team: Optional[str]
    qb_opp: Optional[str]
    wr_te_on_qb_team: int
    bringbacks: int
    uniq_logsum: float              # -sum(log(usage_i)) precomputed
    chalk_sum: float                # sum(usage_i)


# ------------------- Core processing -------------------

def load_lineups(lineups_csv: str) -> pd.DataFrame:
    df = pd.read_csv(lineups_csv)
    # sanity check
    for col in ROSTER_COLS:
        if col not in df.columns:
            raise ValueError(f"Lineups CSV missing required column: {col}")
    return df


def load_projections(proj_csv: str) -> Tuple[pd.DataFrame, str, str, str, Optional[str], Optional[str]]:
    df = pd.read_csv(proj_csv)
    id_col, proj_col, pos_col, team_col, name_col = detect_columns(df)
    # Opponent is optional but useful
    opp_col = None
    for c in ["B_Opponent","Opponent","Opp","OPP","opp"]:
        if c in df.columns:
            opp_col = c
            break
    if opp_col is None:
        candidates = [c for c in df.columns if "opp" in c.lower()]
        opp_col = candidates[0] if candidates else None

    # Standardize names for maps
    rename_map = {id_col:"B_Id", proj_col:"A_ppg_projection", pos_col:"B_Position"}
    if team_col: rename_map[team_col] = "B_Team"
    if opp_col:  rename_map[opp_col]  = "B_Opponent"
    if name_col: rename_map[name_col] = "B_Name"
    std = df.rename(columns=rename_map)

    keep = ["B_Id","A_ppg_projection","B_Position"]
    if "B_Team" in std.columns: keep.append("B_Team")
    if "B_Opponent" in std.columns: keep.append("B_Opponent")
    if "B_Name" in std.columns: keep.append("B_Name")
    std = std[keep].copy()
    return std, "B_Id", "A_ppg_projection", "B_Position", "B_Team" if "B_Team" in std.columns else None, "B_Name" if "B_Name" in std.columns else None


def build_player_maps(proj_df: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, Optional[str]], Dict[str, Optional[str]], Dict[str, Optional[str]]]:
    proj_map, pos_map, team_map, opp_map, name_map = {}, {}, {}, {}, {}
    has_team = "B_Team" in proj_df.columns
    has_opp = "B_Opponent" in proj_df.columns
    has_name = "B_Name" in proj_df.columns
    for _, r in proj_df.iterrows():
        pid = str(r["B_Id"])
        proj_map[pid] = float(r["A_ppg_projection"]) if pd.notna(r["A_ppg_projection"]) else 0.0
        pos_map[pid]  = str(r["B_Position"]) if pd.notna(r["B_Position"]) else ""
        team_map[pid] = (str(r["B_Team"]) if pd.notna(r["B_Team"]) else None) if has_team else None
        opp_map[pid]  = (str(r["B_Opponent"]) if pd.notna(r["B_Opponent"]) else None) if has_opp else None
        name_map[pid] = (str(r["B_Name"]) if pd.notna(r["B_Name"]) else None) if has_name else None
    return proj_map, pos_map, team_map, opp_map, name_map


def compute_pool_usage(lineups_df: pd.DataFrame) -> Dict[str, float]:
    """Usage fraction per player across the entire pool."""
    from collections import Counter
    cnt = Counter()
    total = len(lineups_df)
    for _, r in lineups_df.iterrows():
        for col in ROSTER_COLS:
            pid = extract_player_id(r[col])
            if pid:
                cnt[pid] += 1
    return {pid: c/total for pid, c in cnt.items()}


def make_lineup_objects(lineups_df: pd.DataFrame, proj_map: Dict[str,float],
                        team_map: Dict[str,Optional[str]], opp_map: Dict[str,Optional[str]],
                        pos_map: Dict[str,str], usage: Dict[str,float]) -> List[Lineup]:
    objs = []
    for idx, r in lineups_df.iterrows():
        players_txt = []
        players_id = []
        for col in ROSTER_COLS:
            cell = r[col]
            players_txt.append(str(cell))
            players_id.append(extract_player_id(str(cell)))
        salary = int(r["Budget"]) if "Budget" in r and pd.notna(r["Budget"]) else 0

        # projection sum
        proj_sum = 0.0
        for pid in players_id:
            proj_sum += proj_map.get(pid, 0.0)

        # QB team/opp + count of WR/TE on QB team + bringbacks
        qb_id = players_id[0]  # QB slot
        qb_team = team_map.get(qb_id, None)
        qb_opp  = opp_map.get(qb_id, None)
        wr_te_on = 0
        bringbacks = 0
        if qb_team is not None:
            for pid in players_id[1:]:
                if pos_map.get(pid, "") in ("WR","TE","RB") and team_map.get(pid, None) == qb_team:
                    wr_te_on += 1
        if qb_team is not None and qb_opp is not None:
            for pid in players_id[1:]:
                if team_map.get(pid, None) == qb_opp:
                    bringbacks += 1

        # uniqueness / chalk precompute
        uq = 0.0
        ch = 0.0
        for pid in players_id:
            u = usage.get(pid, 1e-9)
            uq += -math.log(max(1e-9, u))
            ch += u

        objs.append(Lineup(
            idx=idx,
            salary=salary,
            players_id=tuple(players_id),
            players_txt=tuple(players_txt),
            proj_sum=proj_sum,
            qb_team=qb_team,
            qb_opp=qb_opp,
            wr_te_on_qb_team=wr_te_on,
            bringbacks=bringbacks,
            uniq_logsum=uq,
            chalk_sum=ch,
        ))
    return objs


def normalize(values: List[float]) -> List[float]:
    lo = min(values)
    hi = max(values)
    if hi <= lo + 1e-12:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def greedy_select(lineups: List[Lineup], n_target: int = 150,
                  cap_pct: float = 25.0, max_repeat_init: int = 4,
                  w_proj: float = 0.55, w_stack: float = 0.15,
                  w_uniq: float = 0.25, w_chalk: float = 0.05,
                  qb2_bonus: float = 1.0, bring_bonus: float = 0.6,
                  seed: Optional[int] = 42):
    """
    Greedy best-first selection with dynamic reweighting:
    - per-player exposure cap (<= cap_pct of n_target)
    - max repeating players between any two selected (start at 4; relax if needed)
    - no exact duplicates
    Objective blends projection, stack bonuses, uniqueness, and chalk penalty.

    Returns: selected, counts, diagnostics(dict)
    """
    if seed is not None:
        random.seed(seed)

    cap_count = int(math.floor((cap_pct/100.0) * n_target + 1e-9))  # e.g., 37 for 150 @ 25%
    # Base features
    proj_list = [lu.proj_sum for lu in lineups]
    uniq_list = [lu.uniq_logsum for lu in lineups]
    chalk_list = [lu.chalk_sum for lu in lineups]

    proj_norm = normalize(proj_list)
    uniq_norm = normalize(uniq_list)
    chalk_norm = normalize(chalk_list)  # higher is chalkier

    def stack_score(lu: Lineup) -> float:
        return qb2_bonus * (1.0 if lu.wr_te_on_qb_team >= 2 else 0.0) + bring_bonus * (1.0 if lu.bringbacks >= 1 else 0.0)

    base_scores = []
    for i, lu in enumerate(lineups):
        s = (w_proj * proj_norm[i] +
             w_stack * stack_score(lu) +
             w_uniq * uniq_norm[i] -
             w_chalk * chalk_norm[i])
        base_scores.append((s, i))

    # Sort candidates by base score desc
    base_scores.sort(key=lambda x: x[0], reverse=True)
    candidate_idx_order = [i for (_, i) in base_scores]

    selected: List[Lineup] = []
    counts: Dict[str,int] = {}
    seen_sets = set()
    max_repeat = max_repeat_init

    # To limit rescoring cost, consider a moving window from the top
    window = 5000 if len(lineups) > 6000 else len(lineups)

    # Diagnostics
    relaxations = 0

    # Loop until we have n_target or exhausted
    ptr = 0
    stalled = 0
    while len(selected) < n_target and ptr < len(candidate_idx_order):
        batch = candidate_idx_order[ptr: ptr+window]
        best_i = None
        best_score = -1e18

        for i in batch:
            lu = lineups[i]
            # hard constraints
            if not passes_caps(lu, selected, counts, cap_count, max_repeat, seen_sets):
                continue

            # dynamic penalty for nearing exposure caps (encourage breadth)
            pen = 0.0
            for pid in lu.players_id:
                c = counts.get(pid, 0)
                u = c / max(1, cap_count)
                pen += u*u  # quadratic
            # adjust current score
            s = base_scores[i][0] - 0.05 * pen  # small penalty weight

            if s > best_score:
                best_score = s
                best_i = i

        if best_i is not None:
            lu = lineups[best_i]
            selected.append(lu)
            # update counts & seen set
            pset = frozenset(lu.players_id)
            seen_sets.add(pset)
            for pid in lu.players_id:
                counts[pid] = counts.get(pid, 0) + 1
            stalled = 0
        else:
            # no pick in this window -> relax repeat constraint or move window
            stalled += 1
            if stalled >= 3 and max_repeat < 6:
                max_repeat += 1
                relaxations += 1
                stalled = 0
            else:
                ptr += window  # advance to next slice

    diagnostics = {
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
    return selected, counts, diagnostics


def passes_caps(lu: Lineup, selected: List[Lineup], counts: Dict[str,int],
                cap_count: int, max_repeat: int, seen_sets: set) -> bool:
    # exposure caps
    for pid in lu.players_id:
        if counts.get(pid, 0) + 1 > cap_count:
            return False
    # uniqueness: overlap with existing selections
    lu_set = set(lu.players_id)
    for ch in selected:
        if overlap_count(lu_set, ch.players_id) > max_repeat:
            return False
    # no exact duplicates
    if frozenset(lu.players_id) in seen_sets:
        return False
    return True


def overlap_count(a: set, b: Tuple[str, ...]) -> int:
    cnt = 0
    for x in b:
        if x in a:
            cnt += 1
    return cnt


# ------------------- Export -------------------

def export_fanduel(template_csv: str, selected: List[Lineup], out_csv: str):
    """Write selected lineups using the same column order as the template."""
    tdf = pd.read_csv(template_csv, nrows=0)
    template_cols = list(tdf.columns)
    # ensure roster columns exist; if not, fallback to standard roster order
    cols = [c for c in template_cols if c in ROSTER_COLS]
    if not cols:
        cols = ROSTER_COLS[:]
        template_cols = cols  # only roster cols

    # Build output rows
    rows = []
    for lu in selected:
        row = {c: "" for c in template_cols}
        # Map roster
        mapping = dict(zip(ROSTER_COLS, lu.players_txt))
        for c in cols:
            row[c] = mapping.get(c, "")
        rows.append(row)

    out_df = pd.DataFrame(rows, columns=template_cols)
    out_df.to_csv(out_csv, index=False)


def export_usage_report(selected: List[Lineup], full_usage: Dict[str,float],
                        out_csv: str, name_map: Dict[str, Optional[str]],
                        fallback_names: Dict[str, str]):
    """Create usage report comparing selected 150 vs full 50k pool, with player names."""
    from collections import Counter
    sel_cnt = Counter()
    for lu in selected:
        for pid in lu.players_id:
            sel_cnt[pid] += 1
    # Build table
    recs = []
    n_sel = len(selected)
    for pid, sel_n in sel_cnt.items():
        sel_pct = sel_n / max(1, n_sel)
        pool_pct = full_usage.get(pid, 0.0)
        name = name_map.get(pid) or fallback_names.get(pid) or ""
        recs.append({
            "player_id": pid,
            "player_name": name,
            "selected_count": sel_n,
            "selected_pct": sel_pct,
            "pool_pct": pool_pct,
            "delta_pct": sel_pct - pool_pct
        })
    rep = pd.DataFrame(recs).sort_values("selected_pct", ascending=False)
    rep.to_csv(out_csv, index=False)


def write_summary(out_path: str, diagnostics: dict, counts: Dict[str,int], n_target: int):
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
        f.write("\nStack Distribution (out of selected):\n")
        f.write(f"  QB+2: {diagnostics.get('qb2_count', 0)}\n")
        f.write(f"  Bring-back >=1: {diagnostics.get('bringback_count', 0)}\n")
        f.write(f"  Both (QB+2 & Bring-back): {diagnostics.get('both_qb2_and_bring', 0)}\n")


# ------------------- Main CLI -------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lineups", type=str, help="Path to lineup pool CSV")
    ap.add_argument("--projections", type=str, help="Path to projections CSV")
    ap.add_argument("--template", type=str, help="Path to FanDuel template CSV")
    ap.add_argument("--out-prefix", type=str, default="mme150")
    ap.add_argument("--out-dir", type=str, default="autoMME", help="Output folder (default: autoMME)")
    ap.add_argument("--cap", type=float, default=25.0, help="Max exposure percent per player (default 25)")
    ap.add_argument("--repeat", type=int, default=4, help="Max repeating players between any two selected (start)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    lineups_csv = args.lineups or pick_file_cli_or_gui("Select LINEUPS CSV")
    proj_csv    = args.projections or pick_file_cli_or_gui("Select PROJECTIONS CSV")
    templ_csv   = args.template or pick_file_cli_or_gui("Select FanDuel TEMPLATE CSV")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading...")
    ldf = load_lineups(lineups_csv)
    pdf, idcol, projcol, poscol, teamcol, namecol = load_projections(proj_csv)

    print("Building maps...")
    proj_map, pos_map, team_map, opp_map, name_map = build_player_maps(pdf)

    print("Computing pool usage...")
    usage = compute_pool_usage(ldf)

    print("Making lineup objects...")
    lineup_objs = make_lineup_objects(ldf, proj_map, team_map, opp_map, pos_map, usage)

    print(f"Selecting 150 (cap={args.cap}%, repeat_start={args.repeat})...")
    selected, counts, diagnostics = greedy_select(lineup_objs, n_target=150, cap_pct=args.cap, max_repeat_init=args.repeat, seed=args.seed)

    # Fallback names from lineup texts if missing in projections
    fallback_names = {}
    for lu in selected:
        for cell_txt, pid in zip(lu.players_txt, lu.players_id):
            if pid not in name_map or not name_map.get(pid):
                nm = extract_player_name(cell_txt)
                if nm:
                    fallback_names[pid] = nm

    out_prefix = Path(args.out_prefix).stem
    out_upload = out_dir / f"{out_prefix}_fanduel_upload.csv"
    out_usage  = out_dir / f"{out_prefix}_usage_report.csv"
    out_summary= out_dir / f"{out_prefix}_summary.txt"

    print(f"Writing FanDuel upload CSV -> {out_upload}")
    export_fanduel(templ_csv, selected, str(out_upload))

    print(f"Writing Usage report -> {out_usage}")
    export_usage_report(selected, usage, str(out_usage), name_map, fallback_names)

    print(f"Writing Summary -> {out_summary}")
    write_summary(str(out_summary), diagnostics, counts, n_target=150)

    # final console summary
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
