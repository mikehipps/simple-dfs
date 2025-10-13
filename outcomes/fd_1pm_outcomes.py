#!/usr/bin/env python3
"""
FanDuel outcomes for '1:00 pm ET' Sunday slate
- Date default: yesterday (relative to local time); override with --date YYYY-MM-DD
- Source: nflverse weekly player stats + schedules (public releases)
- Scoring: FanDuel 0.5-PPR + 3-pt bonuses (300 pass / 100 rush / 100 recv), DST + K included
"""

import argparse, sys, math
from datetime import datetime, timedelta, timezone
import pandas as pd

# ---- Settings (change if you want) ----
SEASON = 2025                                  # season to pull
TZ_ET = "America/New_York"
SLATE_HOUR_LOCAL = 13                          # 1:00 pm local (ET)
ALLOW_MINUTE_WINDOW = {0, 1, 5}                # accept 1:00, 1:01, 1:05 oddities

# ---- NFLVERSE release URLs (CSV/Parquet). Using CSV keeps deps light (no pyarrow). ----
# schedules_<season>.csv has kickoff timestamps and game_ids
SCHEDULE_URL = f"https://github.com/nflverse/nflverse-data/releases/download/schedules/schedules_{SEASON}.csv"
# stats_player_<season>.csv has weekly player-level boxscore-like stats (offense/defense/kicking together)
STATS_URL    = f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_{SEASON}.csv"

def _load_schedules_df():
    import pandas as pd
    # try nflverse release (single file; sometimes only RDS/parquet exist)
    try:
        url1 = "https://github.com/nflverse/nflverse-data/releases/download/schedules/schedules.csv"
        return pd.read_csv(url1, low_memory=False)
    except Exception:
        # fallback: Lee Sharpe’s nfldata games.csv
        url2 = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
        return pd.read_csv(url2, low_memory=False)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Slate date (YYYY-MM-DD). Default = yesterday in ET.")
    ap.add_argument("--out", default="fd_1pm_outcomes.csv", help="Output CSV filename")
    return ap.parse_args()

def infer_date_et(arg_date: str | None) -> datetime:
    import pytz
    et = pytz.timezone(TZ_ET)
    if arg_date:
        d = datetime.strptime(arg_date, "%Y-%m-%d")
        return et.localize(datetime(d.year, d.month, d.day))
    # default: yesterday ET
    now_et = datetime.now(et)
    y = now_et - timedelta(days=1)
    return et.localize(datetime(y.year, y.month, y.day))

def load_slate_game_ids(slate_dt_et: datetime) -> set[str]:
    # load schedules
    sch = _load_schedules_df()
    # columns differ across years; prefer game_start_time (UTC) if present else use gameday/gametime
    # Normalize to localized ET date/hour
    if "game_start_time" in sch.columns:  # ISO timestamp (UTC)
        ts = pd.to_datetime(sch["game_start_time"], utc=True, errors="coerce")
    else:
        # fall back: combine gameday+gametime (string)
        ts = pd.to_datetime(
            sch["gameday"].astype(str) + " " + sch["gametime"].astype(str),
            utc=True, errors="coerce"
        )
    # convert to ET
    ts_et = ts.dt.tz_convert(TZ_ET)
    sch = sch.assign(ts_et=ts_et)

    # same calendar date as slate_dt_et, and hour==13 (1pm), allow a few minute quirks
    same_day = (sch["ts_et"].dt.date == slate_dt_et.date())
    hour_ok = (sch["ts_et"].dt.hour == SLATE_HOUR_LOCAL)
    minute_ok = sch["ts_et"].dt.minute.isin(ALLOW_MINUTE_WINDOW)

    mask = same_day & hour_ok & minute_ok
    gids = set(sch.loc[mask, "game_id"].astype(str))
    if not gids:
        raise SystemExit(f"No 1:00 pm ET games found on {slate_dt_et.date()}.")
    return gids

def load_weekly_player_stats() -> pd.DataFrame:
    df = pd.read_csv(STATS_URL, low_memory=False)
    # ensure types
    for c in ("season","week"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # keep REG season rows only
    if "season_type" in df.columns:
        df = df[df["season_type"] == "REG"]
    return df

def fanduel_points(row: pd.Series) -> float:
    # Base components (missing columns treated as 0)
    g = lambda c: float(row.get(c, 0) or 0)

    # Offense (0.5 PPR with 3-pt bonuses; sacks against QB don’t subtract FD points)
    pass_y = g("passing_yards")
    pass_td = g("passing_tds")
    pass_int = g("passing_interceptions")

    rush_y = g("rushing_yards")
    rush_td = g("rushing_tds")

    rec = g("receptions")
    rec_y = g("receiving_yards")
    rec_td = g("receiving_tds")

    fumbles_lost = g("fumbles_lost") or g("rushing_fumbles_lost") or g("receiving_fumbles_lost")

    # Kicking
    fgm_0_39 = g("kicking_fg_made_0_39")
    fgm_40_49 = g("kicking_fg_made_40_49")
    fgm_50p  = g("kicking_fg_made_50_plus")
    xpm      = g("kicking_xpm")

    # DST (team stats are duplicated for each DST player row in this table; most workflows use team-level DST files,
    # but this keeps it simple if present per player/team)
    sacks = g("defense_sacks")
    dst_int = g("defense_interceptions")
    fum_rec = g("defense_fumbles_recovered")
    safeties = g("defense_safeties")
    dst_td = g("defense_tds")
    kr_pr_td = g("special_teams_tds") or g("kick_return_tds") + g("punt_return_tds")

    # Points allowed buckets—some tables encode as 'points_allowed'; if not present, set 0
    pa = g("points_allowed")

    # ---- FanDuel scoring ----
    pts = 0.0
    # QB
    pts += pass_y / 25.0
    pts += 4.0 * pass_td
    pts += -2.0 * pass_int
    # Rushing / Receiving
    pts += rush_y / 10.0
    pts += 6.0 * rush_td
    pts += 0.5 * rec
    pts += rec_y / 10.0
    pts += 6.0 * rec_td
    # Fumbles lost
    pts += -2.0 * fumbles_lost
    # Yardage bonuses (2024+ update)
    pts += 3.0 if pass_y >= 300.0 else 0.0
    pts += 3.0 if rush_y >= 100.0 else 0.0
    pts += 3.0 if rec_y  >= 100.0 else 0.0
    # Kicking
    pts += 3.0 * (fgm_0_39 + fgm_40_49) + 5.0 * fgm_50p + 1.0 * xpm
    # DST (if present as player rows; often you’ll compute DST separately)
    if pa:
        # FanDuel PA buckets
        if pa == 0: pts += 10
        elif 1 <= pa <= 6: pts += 7
        elif 7 <= pa <= 13: pts += 4
        elif 14 <= pa <= 20: pts += 1
        elif 21 <= pa <= 27: pts += 0
        elif 28 <= pa <= 34: pts += -1
        else: pts += -4
    pts += sacks * 1.0 + dst_int * 2.0 + fum_rec * 2.0 + safeties * 2.0
    pts += 6.0 * (dst_td + kr_pr_td)

    return round(pts, 2)

def main():
    args = parse_args()
    slate_dt = infer_date_et(args.date)

    # 1) Which games were 1:00 pm ET on that date?
    game_ids = load_slate_game_ids(slate_dt)

    # 2) Load weekly player stats and filter to those game_ids
    stats = load_weekly_player_stats()
    stats = stats[(stats["season"] == SEASON) & (stats["game_id"].astype(str).isin(game_ids))].copy()

    # 3) Compute FD points
    stats["fd_points"] = stats.apply(fanduel_points, axis=1)

    # 4) Choose friendly columns
    keep_cols = [
        "season","week","game_id","team","opponent_team",
        "player_id","player_display_name","position","position_group",
        "passing_yards","passing_tds","passing_interceptions",
        "rushing_yards","rushing_tds",
        "receptions","receiving_yards","receiving_tds",
        "fumbles_lost",
        "kicking_fg_made_0_39","kicking_fg_made_40_49","kicking_fg_made_50_plus","kicking_xpm",
        "defense_sacks","defense_interceptions","defense_fumbles_recovered","defense_safeties",
        "defense_tds","kick_return_tds","punt_return_tds","points_allowed",
        "fd_points"
    ]
    exist_cols = [c for c in keep_cols if c in stats.columns]
    out = stats[exist_cols].sort_values(["team","player_display_name","position"], na_position="last")
    out.to_csv(args.out, index=False)
    print(f"Wrote {len(out)} rows → {args.out}")

if __name__ == "__main__":
    main()
