"""
Sport Helpers Module

Provides sport-specific helper classes for lineup optimization constraints and configurations.
Each sport helper implements standardized interfaces for applying constraints, budgets, and validations.
"""

from sport_helpers.base import SportHelper
from sport_helpers.nfl import NFLHelper
from sport_helpers.nhl import NHLHelper
from sport_helpers.nba import NBAHelper

__all__ = [
    'SportHelper',
    'NFLHelper',
    'NHLHelper',
    'NBAHelper',
]

# Sport registry for dynamic helper loading
SPORT_REGISTRY = {
    'FOOTBALL': NFLHelper,
    'NFL': NFLHelper,
    'HOCKEY': NHLHelper,
    'NHL': NHLHelper,
    'BASKETBALL': NBAHelper,
    'NBA': NBAHelper,
}


def get_sport_helper(sport_type):
    """
    Get the appropriate sport helper class based on sport type.
    
    Args:
        sport_type (str): Sport type identifier (e.g., 'FOOTBALL', 'NFL', 'HOCKEY', etc.)
        
    Returns:
        SportHelper: Sport helper class for the specified sport type
        
    Raises:
        ValueError: If sport type is not supported
    """
    sport_type_upper = sport_type.upper()
    if sport_type_upper in SPORT_REGISTRY:
        return SPORT_REGISTRY[sport_type_upper]
    else:
        raise ValueError(f"Unsupported sport type: {sport_type}. Supported types: {list(SPORT_REGISTRY.keys())}")