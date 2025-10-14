"""
Custom Random Fantasy Points Strategy for NFL Lineup Optimization
Extracted from pydfs-lineup-optimizer module to maintain custom non-uniform distribution logic
"""

from typing import Dict
from random import uniform, random
import math
from pydfs_lineup_optimizer.player import Player
from pydfs_lineup_optimizer.lineup import Lineup
from pydfs_lineup_optimizer.fantasy_points_strategy import BaseFantasyPointsStrategy


class CustomRandomFantasyPointsStrategy(BaseFantasyPointsStrategy):
    """
    Custom random fantasy points strategy with non-uniform distribution
    that skews toward lower multipliers (65% probability of multiplier <= 1.0)
    
    This strategy provides more realistic randomization by favoring conservative
    projections while still allowing for upside potential.
    """
    
    def __init__(self, min_deviation: float = 0.0, max_deviation: float = 0.12):
        """
        Initialize the custom random strategy
        
        Args:
            min_deviation (float): Minimum deviation multiplier (default: 0.0)
            max_deviation (float): Maximum deviation multiplier (default: 0.12)
        """
        self.min_deviation = min_deviation
        self.max_deviation = max_deviation

    def get_player_fantasy_points(self, player: Player) -> float:
        """
        Get randomized fantasy points for a player using non-uniform distribution
        
        Args:
            player (Player): The player to get fantasy points for
            
        Returns:
            float: Randomized fantasy points value
        """
        proj = player.fppg
        
        # Use floor/ceil if available for direct uniform sampling
        if player.fppg_floor is not None and player.fppg_ceil is not None:
            return uniform(player.fppg_floor, player.fppg_ceil)

        # 1) pick deviation d from [min,max]
        d = uniform(
            player.min_deviation if player.min_deviation is not None else self.min_deviation,
            player.max_deviation if player.max_deviation is not None else self.max_deviation
        )

        # 2) bounds in multiplier space; clamp low at 0 for huge d (e.g., 4.0)
        a = max(0.0, 1.0 - d)
        b = 1.0 + d

        # 3) choose exponent k so that P(mult <= 1) = 0.65 exactly
        q = (1.0 - a) / (b - a)                 # fraction of [a,b] that lies <= 1
        k = math.log(q) / math.log(0.65)        # k > 0
        mult = a + (b - a) * (random() ** k)    # skewed toward a, with 65% mass <= 1

        return proj * mult

    def set_previous_lineup(self, lineup: Lineup):
        """
        Set the previous lineup (inherited from BaseFantasyPointsStrategy)
        
        Args:
            lineup (Lineup): The previous lineup
        """
        pass