from __future__ import annotations

from collections import Counter
from typing import List

from .base import (
    LineupContext,
    LineupFeatures,
    PickerDefaults,
    PickerHelper,
    ScoreWeights,
    SummaryContext,
)


class NFLPickerHelper(PickerHelper):
    key = "nfl"
    name = "NFL"
    roster_columns = (
        "QB",
        "RB",
        "RB.1",
        "WR",
        "WR.1",
        "WR.2",
        "TE",
        "FLEX",
        "DEF",
    )

    QB2_BONUS = 1.0
    BRING_BONUS = 0.6

    def defaults(self) -> PickerDefaults:
        return PickerDefaults(
            n_target=150,
            cap_pct=50.0,
            max_repeat_init=7,
            max_repeat_limit=9,
            min_usage_pct=1.0,
            breadth_penalty=0.05,
            stalled_threshold=3,
            selection_window=5000,
            weights=ScoreWeights(
                projection=0.55,
                correlation=0.25,
                uniqueness=0.45,
                chalk=0.05,
            ),
        )

    def compute_lineup_features(self, ctx: LineupContext) -> LineupFeatures:
        maps = ctx.player_maps
        qb_id = None
        for pid, label in zip(ctx.players_id, ctx.slot_labels):
            pos = maps.position.get(pid, label).upper()
            if pos == "QB":
                qb_id = pid
                break
        if qb_id is None:
            return LineupFeatures(correlation_score=0.0, tags={})

        qb_team = maps.team.get(qb_id)
        qb_opp = maps.opponent.get(qb_id)

        stack_positions = {"WR", "TE", "RB"}
        teammates = 0
        bringbacks = 0
        for pid in ctx.players_id:
            if pid == qb_id:
                continue
            pos = maps.position.get(pid, "").upper()
            team = maps.team.get(pid)
            if qb_team and pos in stack_positions and team == qb_team:
                teammates += 1
            if qb_opp and team == qb_opp:
                bringbacks += 1

        stack_score = 0.0
        if teammates >= 2:
            stack_score += self.QB2_BONUS
        if bringbacks >= 1:
            stack_score += self.BRING_BONUS

        tags = {
            "qb_team": qb_team,
            "qb_opponent": qb_opp,
            "double_stack": teammates >= 2,
            "bringbacks": bringbacks,
            "teammates_count": teammates,
        }
        return LineupFeatures(correlation_score=stack_score, tags=tags)

    def summary_lines(self, ctx: SummaryContext) -> List[str]:
        total = len(ctx.selected)
        if total == 0:
            return []
        double_count = sum(1 for lu in ctx.selected if lu.features.tags.get("double_stack"))
        bring_count = sum(1 for lu in ctx.selected if lu.features.tags.get("bringbacks", 0) >= 1)
        both_count = sum(
            1
            for lu in ctx.selected
            if lu.features.tags.get("double_stack") and lu.features.tags.get("bringbacks", 0) >= 1
        )
        lines = [
            f"QB double stacks: {double_count}/{total}",
            f"Bring-backs: {bring_count}/{total}",
            f"Double+bring: {both_count}/{total}",
        ]
        team_counter: Counter = Counter()
        for lu in ctx.selected:
            team = lu.features.tags.get("qb_team")
            if team:
                team_counter[team] += 1
        if team_counter:
            top = ", ".join(f"{team}:{count}" for team, count in team_counter.most_common(5))
            lines.append(f"Top QB teams: {top}")
        return lines
