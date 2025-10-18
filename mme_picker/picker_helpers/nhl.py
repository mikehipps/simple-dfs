from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple

from argparse import Namespace

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
    def __init__(self) -> None:
        self.power_play_bonus_enabled = True
        self.power_play_pair_bonus = 0.35
        self.line_bonus_enabled = True
        self.line_pair_bonus = 0.25

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

    def configure(self, args: Namespace) -> None:
        if getattr(args, "disable_pp_bonus", False):
            self.power_play_bonus_enabled = False
        else:
            self.power_play_bonus_enabled = True
            if getattr(args, "pp_bonus", None) is not None:
                self.power_play_pair_bonus = float(args.pp_bonus)
        if getattr(args, "disable_line_bonus", False):
            self.line_bonus_enabled = False
        else:
            self.line_bonus_enabled = True
            if getattr(args, "line_bonus", None) is not None:
                self.line_pair_bonus = float(args.line_bonus)

    def compute_lineup_features(self, ctx: LineupContext) -> LineupFeatures:
        maps = ctx.player_maps
        skater_team_counts: Counter = Counter()
        game_team_sets: Dict[str, Set[str]] = defaultdict(set)
        power_play_groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        even_line_groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)

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
                line_val = maps.line.get(pid)
                if line_val:
                    even_line_groups[(team, line_val)].append(pid)
                roster_order = maps.roster_order.get(pid) or ""
                pp_val = maps.pp_line.get(pid)
                pp_key = None
                if pp_val:
                    pp_key = str(pp_val)
                elif roster_order:
                    upper = roster_order.upper()
                    if "POWER PLAY" in upper:
                        pp_key = upper.split()[-1].strip("#")
                if pp_key:
                    power_play_groups[(team, pp_key)].append(pid)

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

        even_pairs_total = 0
        even_bonus = 0.0
        if self.line_bonus_enabled and self.line_pair_bonus:
            for (team, unit), players in even_line_groups.items():
                count = len(players)
                if count >= 2:
                    pairs = count * (count - 1) // 2
                    even_pairs_total += pairs
                    even_bonus += self.line_pair_bonus * pairs
            stack_score += even_bonus

        pp_pairs_total = 0
        pp_bonus = 0.0
        if self.power_play_bonus_enabled and self.power_play_pair_bonus:
            for (team, unit), players in power_play_groups.items():
                count = len(players)
                if count >= 2:
                    pairs = count * (count - 1) // 2
                    pp_pairs_total += pairs
                    pp_bonus += self.power_play_pair_bonus * pairs
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
            "power_play_bonus_value": self.power_play_pair_bonus if self.power_play_bonus_enabled else 0.0,
            "line_pairs": even_pairs_total,
            "line_bonus": even_bonus,
            "line_bonus_value": self.line_pair_bonus if self.line_bonus_enabled else 0.0,
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
        line_pairs_total = 0
        line_bonus_total = 0.0
        pp_pairs_total = 0
        pp_bonus_total = 0.0
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
            line_pairs_total += lu.features.tags.get("line_pairs", 0)
            line_bonus_total += lu.features.tags.get("line_bonus", 0.0)
            pp_pairs_total += lu.features.tags.get("power_play_pairs", 0)
            pp_bonus_total += lu.features.tags.get("power_play_bonus", 0.0)
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
        if self.line_bonus_enabled:
            lines.append(
                f"Line pairs: {line_pairs_total} pairings (+{line_bonus_total:.2f} bonus total, {self.line_pair_bonus:.2f} each)."
            )
        else:
            lines.append("Line bonus: disabled.")
        if self.power_play_bonus_enabled:
            lines.append(
                f"Power-play pairs: {pp_pairs_total} pairings (+{pp_bonus_total:.2f} bonus total, {self.power_play_pair_bonus:.2f} each)."
            )
        else:
            lines.append("Power-play bonus: disabled.")
        return lines
