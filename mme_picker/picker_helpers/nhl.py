from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple

from .base import (
    LineupContext,
    LineupFeatures,
    PickerDefaults,
    PickerHelper,
    ScoreWeights,
    SummaryContext,
)


class NHLPickerHelper(PickerHelper):
    key = "nhl"
    name = "NHL"
    roster_columns = (
        "C",
        "C.1",
        "W",
        "W.1",
        "D",
        "D.1",
        "UTIL",
        "UTIL.1",
        "G",
    )

    def defaults(self) -> PickerDefaults:
        return PickerDefaults(
            n_target=150,
            cap_pct=40.0,
            max_repeat_init=5,
            max_repeat_limit=7,
            min_usage_pct=4.0,
            breadth_penalty=0.045,
            stalled_threshold=3,
            selection_window=5000,
            weights=ScoreWeights(
                projection=0.55,
                correlation=0.40,
                uniqueness=0.25,
                chalk=0.20,
            ),
        )

    def compute_lineup_features(self, ctx: LineupContext) -> LineupFeatures:
        maps = ctx.player_maps
        skater_team_counts: Counter = Counter()
        game_team_sets: Dict[str, Set[str]] = defaultdict(set)
        power_play_groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)

        goalie_ids = [
            pid for pid in ctx.players_id if maps.position.get(pid, "").upper() == "G"
        ]
        goalie_id = goalie_ids[0] if goalie_ids else None
        goalie_team = maps.team.get(goalie_id) if goalie_id else None
        goalie_opp = maps.opponent.get(goalie_id) if goalie_id else None

        for pid in ctx.players_id:
            pos = maps.position.get(pid, "").upper()
            team = maps.team.get(pid)
            if pos != "G" and team:
                skater_team_counts[team] += 1
                game = maps.game.get(pid)
                if game:
                    game_team_sets[game].add(team)
                roster_order = (maps.roster_order.get(pid) or "").upper()
                if roster_order.startswith("POWER PLAY"):
                    power_play_groups[(team, roster_order)].append(pid)

        stack_score = 0.0
        pair_stacks = 0
        triple_stacks = 0
        max_stack = max(skater_team_counts.values()) if skater_team_counts else 0
        for count in skater_team_counts.values():
            if count >= 4:
                triple_stacks += 1
                stack_score += 1.6 + 0.25 * (count - 4)
            elif count == 3:
                triple_stacks += 1
                stack_score += 1.1
            elif count == 2:
                pair_stacks += 1
                stack_score += 0.45

        cross_games = sum(1 for teams in game_team_sets.values() if len(teams) >= 2)
        stack_score += 0.35 * cross_games

        pp_pairs_total = 0
        pp_bonus = 0.0
        POWER_PLAY_PAIR_BONUS = 0.35
        for (team, unit), players in power_play_groups.items():
            count = len(players)
            if count >= 2:
                pairs = count * (count - 1) // 2
                pp_pairs_total += pairs
                pp_bonus += POWER_PLAY_PAIR_BONUS * pairs
        stack_score += pp_bonus

        goalie_support = 0
        goalie_conflict = 0
        if goalie_id:
            for pid in ctx.players_id:
                if pid == goalie_id:
                    continue
                team = maps.team.get(pid)
                if team == goalie_team:
                    goalie_support += 1
                if team == goalie_opp:
                    goalie_conflict += 1
            stack_score += 0.18 * goalie_support
            stack_score -= 0.65 * goalie_conflict

        tags = {
            "max_stack": max_stack,
            "pair_stacks": pair_stacks,
            "triple_stacks": triple_stacks,
            "cross_games": cross_games,
            "goalie_support": goalie_support,
            "goalie_conflict": goalie_conflict,
            "power_play_pairs": pp_pairs_total,
            "power_play_bonus": pp_bonus,
        }
        return LineupFeatures(correlation_score=stack_score, tags=tags)

    def summary_lines(self, ctx: SummaryContext) -> List[str]:
        total = len(ctx.selected)
        if total == 0:
            return []
        stack_counts: Counter = Counter()
        triple_total = 0
        pair_total = 0
        cross_total = 0
        goalie_conflicts = 0
        goalie_conflict_lineups = 0
        pp_pairs_total = 0
        for lu in ctx.selected:
            max_stack = lu.features.tags.get("max_stack", 0)
            stack_counts[max_stack] += 1
            triple_total += lu.features.tags.get("triple_stacks", 0)
            pair_total += lu.features.tags.get("pair_stacks", 0)
            cross_total += lu.features.tags.get("cross_games", 0)
            conflict = lu.features.tags.get("goalie_conflict", 0)
            if conflict:
                goalie_conflicts += conflict
                goalie_conflict_lineups += 1
            pp_pairs_total += lu.features.tags.get("power_play_pairs", 0)
        stack_summary = ", ".join(
            f"{size}-man:{count}" for size, count in sorted(stack_counts.items(), reverse=True)
        )
        lines = [
            f"Max stack sizes seen: {stack_summary or 'n/a'}.",
            f"Cross-game mini-stacks: {cross_total} total instances.",
        ]
        lines.append(
            f"Goalie conflicts: {goalie_conflicts} skaters across {goalie_conflict_lineups} lineups."
        )
        if pp_pairs_total:
            lines.append(f"Power-play pairs: {pp_pairs_total} total pairings benefited from bonuses.")
        return lines
