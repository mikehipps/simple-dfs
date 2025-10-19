"""
NFL Sport Helper

NFL-specific helper implementation with D/ST vs opposing QB/RB constraints,
projection randomization hooks, and NFL-specific budget/configuration settings.
"""

import logging
from collections import defaultdict
from random import Random

from sport_helpers.base import SportHelper

try:
    import fd_inputs as _cfg
except ImportError:  # pragma: no cover
    _cfg = object()


class NFLHelper(SportHelper):
    """
    NFL-specific helper implementation.
    
    Provides NFL-specific constraints including:
    - D/ST vs opposing QB/RB restriction
    - NFL-specific budget constraints
    - NFL-specific configuration validation
    """
    
    def __init__(self):
        """Initialize NFL helper with default configuration."""
        self.logger = logging.getLogger(__name__)
        self.team_flip_prob = getattr(_cfg, "NFL_TEAM_FLIP_PROB", 0.5)
        self.team_flip_bonus = getattr(_cfg, "NFL_TEAM_FLIP_BONUS", 0.05)
        self.pass_flip_prob = getattr(_cfg, "NFL_PASS_FLIP_PROB", 0.5)
        self.pass_flip_bonus = getattr(_cfg, "NFL_PASS_FLIP_BONUS", 0.05)
        self.rush_flip_prob = getattr(_cfg, "NFL_RUSH_FLIP_PROB", 0.5)
        self.rush_flip_bonus = getattr(_cfg, "NFL_RUSH_FLIP_BONUS", 0.05)
        self.flip_summary = {
            "batches": 0,
            "team_flips": 0,
            "pass_flips": 0,
            "rush_flips": 0,
            "team_players_boosted": 0,
            "pass_players_boosted": 0,
            "rush_players_boosted": 0,
        }
        self._base_fppg = {}
        self._base_floor = {}
        self._base_ceil = {}
    
    def apply_constraints(self, optimizer):
        """
        Apply NFL-specific constraints to the optimizer.
        
        Args:
            optimizer: The pydfs-lineup-optimizer instance to apply constraints to
            
        Returns:
            None
        """
        # Apply D/ST vs opposing QB/RB restriction (migrated from generate_nfl_lineups.py)
        try:
            optimizer.restrict_positions_for_opposing_team(['D'], ['QB', 'RB'])
            self.logger.info("Applied D/ST vs opposing QB/RB restriction")
        except Exception as e:
            self.logger.warning(f"Could not apply D/ST vs opposing QB/RB restriction - {str(e)}")
    
    def get_budget(self):
        """
        Get NFL-specific budget constraint.
        
        Returns:
            int: NFL budget amount (60000 for FanDuel)
        """
        return 60000  # NFL-specific budget for FanDuel
    
    def validate_config(self, config):
        """
        Validate NFL-specific configuration.
        
        Args:
            config (dict): Configuration dictionary to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # NFL-specific validation logic can be added here
        # For now, just return valid
        return True, ""
    
    def get_sport_specific_config(self):
        """
        Get NFL-specific configuration parameters.
        
        Returns:
            dict: Dictionary containing NFL-specific configuration parameters
        """
        return {
            "sport": "NFL",
            "positions": ["QB", "RB", "WR", "TE", "D"],
            "default_budget": 60000,
            "constraints": ["D/ST vs opposing QB/RB restriction"]
        }
    
    def get_min_salary_offset(self):
        """
        Get the minimum salary offset percentage for NFL.
        
        Returns:
            float: Minimum salary offset as a decimal (0.05 for 5% offset)
        """
        return getattr(_cfg, "NFL_MIN_SALARY_OFFSET", getattr(_cfg, "MIN_SALARY_OFFSET", 0.05))
    
    def get_optimizer_settings(self):
        """
        Get NFL-specific optimizer settings.
        
        Returns:
            dict: Dictionary of optimizer settings specific to NFL
        """
        return {
            "use_mip_solver": True,
            "enable_random_strategy": True
        }
    
    def pre_optimization_setup(self, optimizer):
        """
        Perform NFL-specific setup before optimization begins.
        
        Args:
            optimizer: The pydfs-lineup-optimizer instance
            
        Returns:
            None
        """
        self.logger.info("NFL-specific pre-optimization setup completed")
    
    def post_optimization_processing(self, lineups):
        """
        Perform NFL-specific processing after optimization completes.
        
        Args:
            lineups (list): List of generated lineups
            
        Returns:
            list: Processed lineups
        """
        self.logger.info(f"NFL-specific post-processing for {len(lineups)} lineups")
        return lineups

    # ---- random bias helpers -------------------------------------------------
    def apply_random_bias(self, optimizer, rng: Random):
        """
        Apply per-batch random projection bumps to encourage varied team outcomes.

        Coin flips are performed per team for:
            * Team-wide bump (all players)
            * Passing bump (QB/WR/TE)
            * Rushing bump (RB/DST)
        """
        players = optimizer.player_pool.all_players
        if not players:
            return

        # Cache base projections the first time we see players.
        if not self._base_fppg:
            for player in players:
                self._base_fppg[player.id] = player.fppg
                self._base_floor[player.id] = player.fppg_floor
                self._base_ceil[player.id] = player.fppg_ceil

        # Reset projections to original values before applying new randomness.
        for player in players:
            base = self._base_fppg.get(player.id)
            if base is not None:
                player.fppg = base
                if player.id in self._base_floor and self._base_floor[player.id] is not None:
                    player.fppg_floor = self._base_floor[player.id]
                if player.id in self._base_ceil and self._base_ceil[player.id] is not None:
                    player.fppg_ceil = self._base_ceil[player.id]

        team_players = defaultdict(list)
        for player in players:
            team_players[player.team].append(player)

        team_flip = {team: rng.random() < self.team_flip_prob for team in team_players}
        pass_flip = {team: rng.random() < self.pass_flip_prob for team in team_players}
        rush_flip = {team: rng.random() < self.rush_flip_prob for team in team_players}

        pass_positions = {"QB", "WR", "TE"}
        rush_positions = {"RB"}
        defense_positions = {"D", "DST", "DEF"}

        team_players_boosted = 0
        pass_players_boosted = 0
        rush_players_boosted = 0

        for team, players_in_team in team_players.items():
            team_multiplier = 1 + self.team_flip_bonus if team_flip.get(team) else 1
            pass_multiplier = 1 + self.pass_flip_bonus if pass_flip.get(team) else 1
            rush_multiplier = 1 + self.rush_flip_bonus if rush_flip.get(team) else 1

            if team_flip.get(team):
                team_players_boosted += len(players_in_team)
            if pass_flip.get(team):
                pass_players_boosted += sum(
                    1 for player in players_in_team if pass_positions.intersection(player.positions)
                )
            if rush_flip.get(team):
                rush_players_boosted += sum(
                    1
                    for player in players_in_team
                    if rush_positions.intersection(player.positions) or defense_positions.intersection(player.positions)
                )

            for player in players_in_team:
                multiplier = 1.0
                base = self._base_fppg.get(player.id)
                if base is None:
                    continue
                if team_flip.get(team):
                    multiplier *= team_multiplier
                if pass_flip.get(team) and pass_positions.intersection(player.positions):
                    multiplier *= pass_multiplier
                if rush_flip.get(team) and (
                    rush_positions.intersection(player.positions) or defense_positions.intersection(player.positions)
                ):
                    multiplier *= rush_multiplier

                player.fppg = base * multiplier
                if player.id in self._base_floor and self._base_floor[player.id] is not None:
                    player.fppg_floor = self._base_floor[player.id] * multiplier
                if player.id in self._base_ceil and self._base_ceil[player.id] is not None:
                    player.fppg_ceil = self._base_ceil[player.id] * multiplier

        self.flip_summary["batches"] += 1
        self.flip_summary["team_flips"] += sum(1 for hit in team_flip.values() if hit)
        self.flip_summary["pass_flips"] += sum(1 for hit in pass_flip.values() if hit)
        self.flip_summary["rush_flips"] += sum(1 for hit in rush_flip.values() if hit)
        self.flip_summary["team_players_boosted"] += team_players_boosted
        self.flip_summary["pass_players_boosted"] += pass_players_boosted
        self.flip_summary["rush_players_boosted"] += rush_players_boosted

    def get_random_bias_summary(self):
        return dict(self.flip_summary)
