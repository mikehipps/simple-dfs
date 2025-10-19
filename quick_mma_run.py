#!/usr/bin/env python3
"""
Quick MMA FanDuel lineup build (no helper scaffolding)
"""

from pathlib import Path
from pydfs_lineup_optimizer import (
    AfterEachExposureStrategy,
    RandomFantasyPointsStrategy,
    ProgressiveFantasyPointsStrategy,
    StandardFantasyPointsStrategy,
    Site,
    Sport,
    get_optimizer,
)
from collections import defaultdict

# Path to the raw FD export
csv_path = Path("csv-match/inputs/fdmma.csv")

# How many lineups you want
num_lineups = 3000

# Optional tweaks
max_exposure = .35       # e.g. 0.6 for 60% cap
min_salary = 88       # if you want to force spend-up
randomize = False         # enable Min/Max Deviation randomizer

def main():
    optimizer = get_optimizer(Site.FANDUEL, Sport.MMA)
    optimizer.load_players_from_csv(csv_path)
    print(f"Loaded {len(optimizer.player_pool.all_players)} fighters from {csv_path}")

    if min_salary:
        optimizer.set_min_salary_cap(min_salary)

    if randomize:
        optimizer.set_fantasy_points_strategy(RandomFantasyPointsStrategy())
    else:
        optimizer.set_fantasy_points_strategy(ProgressiveFantasyPointsStrategy(0.15))

    optimize_kwargs = {}
    if max_exposure < 1.0:
        optimize_kwargs["max_exposure"] = max_exposure
        optimize_kwargs["exposure_strategy"] = AfterEachExposureStrategy

    print(f"Optimizing {num_lineups} lineups …")
    lineup_iter = optimizer.optimize(num_lineups, **optimize_kwargs)
    lineups = []
    for idx, lineup in enumerate(lineup_iter, 1):
        lineups.append(lineup)
        if idx % 100 == 0:
            print(f"  built {idx} lineups…")

    out_dir = Path("lineups")
    out_dir.mkdir(exist_ok=True)
    out_subdir = out_dir / "mma"
    out_subdir.mkdir(exist_ok=True)
    out_file = out_subdir / f"{csv_path.stem}-lineups.csv"

    with out_file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(",".join([pos.positions[0] for pos in optimizer.settings.positions]) + "\n")
        for lineup in lineups:
            fh.write(",".join(player.id for player in lineup.players) + "\n")

    usage_path = out_subdir / f"{csv_path.stem}-usage.csv"
    usage_counts = defaultdict(int)
    for lineup in lineups:
        for player in lineup.players:
            usage_counts[player.full_name] += 1
    total = len(lineups)
    with usage_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("Player,Times Used,Usage %\n")
        for name, count in sorted(usage_counts.items(), key=lambda x: x[1], reverse=True):
            fh.write(f"{name},{count},{count/total:.4f}\n")

    print(f"Saved {len(lineups)} MMA lineups to {out_file}")

if __name__ == "__main__":
    main()
