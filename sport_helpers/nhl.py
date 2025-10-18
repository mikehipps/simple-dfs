"""NHL-specific helper with projection nudges for correlation-aware randomness."""

import csv
import logging
from collections import defaultdict
from random import Random

from sport_helpers.base import SportHelper

try:
    import fd_inputs as _cfg
except ImportError:  # pragma: no cover
    _cfg = object()


class NHLHelper(SportHelper):
    """
    NHL-specific helper implementation (stub).
    
    This is a placeholder for future NHL-specific constraints and configurations.
    """
    
    def __init__(self):
        """Initialize NHL helper with default configuration."""
        self.logger = logging.getLogger(__name__)
        self.team_bonus = getattr(_cfg, "NHL_TEAM_FLIP_BONUS", 0.05)
        self.line_bonus = getattr(_cfg, "NHL_LINE_FLIP_BONUS", 0.05)
        self.pp_bonus = getattr(_cfg, "NHL_PP_FLIP_BONUS", 0.05)
        self.goalie_bonus = getattr(_cfg, "NHL_GOALIE_LINE1D_BONUS", 0.10)
        self.team_flip_prob = getattr(_cfg, "NHL_TEAM_FLIP_PROB", 0.5)
        self.line_flip_prob = getattr(_cfg, "NHL_LINE_FLIP_PROB", 0.5)
        self.pp_flip_prob = getattr(_cfg, "NHL_PP_FLIP_PROB", 0.5)
        self.flip_summary = {
            "batches": 0,
            "team_hits": 0,
            "line1_hits": 0,
            "line2_hits": 0,
            "pp1_hits": 0,
            "pp2_hits": 0,
            "goalie_bonus_hits": 0,
        }
        self.player_meta = {}
        self._base_fppg = {}
        self._base_floor = {}
        self._base_ceil = {}
    
    def apply_constraints(self, optimizer):
        """
        Apply NHL-specific constraints to the optimizer.
        
        Args:
            optimizer: The pydfs-lineup-optimizer instance to apply constraints to
            
        Returns:
            None
        """
        # NHL-specific constraints will be implemented in future phases
        self.logger.info("NHL-specific constraints applied (stub implementation)")
    
    def get_budget(self):
        """
        Get NHL-specific budget constraint.
        
        Returns:
            int: NHL budget amount (55000 for FanDuel)
        """
        return 55000  # NHL-specific budget for FanDuel
    
    def validate_config(self, config):
        """
        Validate NHL-specific configuration.
        
        Args:
            config (dict): Configuration dictionary to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # NHL-specific validation logic will be implemented in future phases
        return True, ""
    
    def get_sport_specific_config(self):
        """
        Get NHL-specific configuration parameters.
        
        Returns:
            dict: Dictionary containing NHL-specific configuration parameters
        """
        return {
            "sport": "NHL",
            "positions": ["C", "W", "D", "G"],
            "default_budget": 55000,
            "constraints": ["NHL-specific constraints (stub)"]
        }
    
    def get_min_salary_offset(self):
        """
        Get the minimum salary offset percentage for NHL.
        
        Returns:
            float: Minimum salary offset as a decimal (0.05 for 5% offset)
        """
        return 0.05  # 5% offset for NHL
    
    def get_optimizer_settings(self):
        """
        Get NHL-specific optimizer settings.
        
        Returns:
            dict: Dictionary of optimizer settings specific to NHL
        """
        return {
            "use_mip_solver": True,
            "enable_random_strategy": True
        }

    # ---- new behavior ----
    def load_metadata(self, csv_path):
        """Load HockeyLine/HockeyPPLine data from the projections CSV."""
        meta = {}
        try:
            with open(csv_path, newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    pid = row.get("Id")
                    if not pid:
                        continue
                    line_raw = self._normalize_unit(row.get("HockeyLine"))
                    pp_raw = self._normalize_unit(row.get("HockeyPPLine"))
                    meta[pid] = {"line": line_raw, "pp": pp_raw}
        except FileNotFoundError:
            self.logger.warning("NHLHelper: projections CSV not found for metadata: %s", csv_path)
            meta = {}
        self.player_meta = meta
        self.logger.info("NHLHelper: loaded metadata for %d players", len(meta))

    def apply_random_bias(self, optimizer, rng: Random):
        """Apply per-batch random biases to encourage correlated lineups."""
        if not self.player_meta:
            return
        players = optimizer.player_pool.all_players
        if not players:
            return

        # Cache base projections on first call
        if not self._base_fppg:
            for player in players:
                self._base_fppg[player.id] = player.fppg
                self._base_floor[player.id] = player.fppg_floor
                self._base_ceil[player.id] = player.fppg_ceil

        # Reset to base before applying new randomness
        for player in players:
            base = self._base_fppg.get(player.id)
            if base is not None:
                player.fppg = base
                if player.id in self._base_floor and self._base_floor[player.id] is not None:
                    player.fppg_floor = self._base_floor[player.id]
                if player.id in self._base_ceil and self._base_ceil[player.id] is not None:
                    player.fppg_ceil = self._base_ceil[player.id]

        team_players = defaultdict(list)
        team_lines = defaultdict(set)
        team_pps = defaultdict(set)

        for player in players:
            team = player.team
            meta = self.player_meta.get(player.id, {})
            line = meta.get("line")
            pp = meta.get("pp")
            team_players[team].append((player, line, pp))
            if line:
                team_lines[team].add(line)
            if pp:
                team_pps[team].add(pp)

        team_flip = {team: rng.random() < self.team_flip_prob for team in team_players}
        line_flip = {}
        for team, lines in team_lines.items():
            for line in lines:
                line_flip[(team, line)] = line in {"1", "2"} and rng.random() < self.line_flip_prob
        pp_flip = {}
        for team, pps in team_pps.items():
            for pp in pps:
                pp_flip[(team, pp)] = pp in {"1", "2"} and rng.random() < self.pp_flip_prob

        goalie_bonus_teams = set()
        team_hit_counts = 0
        line1_hits = 0
        line2_hits = 0
        pp1_hits = 0
        pp2_hits = 0
        for team in team_players:
            if not team_flip.get(team):
                continue
            team_hit_counts += 1
            has_line = any(line_flip.get((team, line)) for line in team_lines.get(team, []) if line in {"1", "2"})
            has_pp = any(pp_flip.get((team, pp)) for pp in team_pps.get(team, []) if pp in {"1", "2"})
            if has_line and has_pp:
                goalie_bonus_teams.add(team)

        for team, roster in team_players.items():
            for player, line, pp in roster:
                base = self._base_fppg.get(player.id)
                if base is None:
                    continue
                multiplier = 1.0
                if team_flip.get(team):
                    multiplier *= (1 + self.team_bonus)

                line_key = line if line is not None else None
                if line_key in {"1", "2"} and line_flip.get((team, line_key)):
                    multiplier *= (1 + self.line_bonus)
                    if line_key == "1":
                        line1_hits += 1
                    elif line_key == "2":
                        line2_hits += 1

                pp_key = pp if pp is not None else None
                if pp_key in {"1", "2"} and pp_flip.get((team, pp_key)):
                    multiplier *= (1 + self.pp_bonus)
                    if pp_key == "1":
                        pp1_hits += 1
                    elif pp_key == "2":
                        pp2_hits += 1

                # Apply goalie/line1D bonus if all flips hit for the team
                if team in goalie_bonus_teams:
                    if "G" in player.positions or (line_key == "1" and "D" in player.positions):
                        multiplier *= (1 + self.goalie_bonus)

                player.fppg = base * multiplier
                if player.id in self._base_floor and self._base_floor[player.id] is not None:
                    player.fppg_floor = self._base_floor[player.id] * multiplier
                if player.id in self._base_ceil and self._base_ceil[player.id] is not None:
                    player.fppg_ceil = self._base_ceil[player.id] * multiplier

        self.flip_summary["batches"] += 1
        self.flip_summary["team_hits"] += team_hit_counts
        self.flip_summary["line1_hits"] += line1_hits
        self.flip_summary["line2_hits"] += line2_hits
        self.flip_summary["pp1_hits"] += pp1_hits
        self.flip_summary["pp2_hits"] += pp2_hits
        self.flip_summary["goalie_bonus_hits"] += len(goalie_bonus_teams)

    def get_random_bias_summary(self):
        return dict(self.flip_summary)

    @staticmethod
    def _normalize_unit(value):
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        try:
            # Handle values like 1.0, 2.0, "3"
            return str(int(float(text)))
        except (ValueError, TypeError):
            return text

    @staticmethod
    def _to_int(value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
