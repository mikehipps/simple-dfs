"""
NBA Sport Helper

NBA-specific helper implementation (stub for now).
Will be implemented in future phases.
"""

import logging
from sport_helpers.base import SportHelper

try:
    import fd_inputs as _cfg
except ImportError:  # pragma: no cover
    _cfg = object()


class NBAHelper(SportHelper):
    """
    NBA-specific helper implementation (stub).
    
    This is a placeholder for future NBA-specific constraints and configurations.
    """
    
    def __init__(self):
        """Initialize NBA helper with default configuration."""
        self.logger = logging.getLogger(__name__)
    
    def apply_constraints(self, optimizer):
        """
        Apply NBA-specific constraints to the optimizer.
        
        Args:
            optimizer: The pydfs-lineup-optimizer instance to apply constraints to
            
        Returns:
            None
        """
        # NBA-specific constraints will be implemented in future phases
        self.logger.info("NBA-specific constraints applied (stub implementation)")
    
    def get_budget(self):
        """
        Get NBA-specific budget constraint.
        
        Returns:
            int: NBA budget amount (60000 for FanDuel)
        """
        return 60000  # NBA-specific budget for FanDuel
    
    def validate_config(self, config):
        """
        Validate NBA-specific configuration.
        
        Args:
            config (dict): Configuration dictionary to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # NBA-specific validation logic will be implemented in future phases
        return True, ""
    
    def get_sport_specific_config(self):
        """
        Get NBA-specific configuration parameters.
        
        Returns:
            dict: Dictionary containing NBA-specific configuration parameters
        """
        return {
            "sport": "NBA",
            "positions": ["PG", "SG", "SF", "PF", "C"],
            "default_budget": 60000,
            "constraints": ["NBA-specific constraints (stub)"]
        }
    
    def get_min_salary_offset(self):
        """
        Get the minimum salary offset percentage for NBA.
        
        Returns:
            float: Minimum salary offset as a decimal (0.05 for 5% offset)
        """
        return getattr(_cfg, "NBA_MIN_SALARY_OFFSET", getattr(_cfg, "MIN_SALARY_OFFSET", 0.05))
    
    def get_optimizer_settings(self):
        """
        Get NBA-specific optimizer settings.
        
        Returns:
            dict: Dictionary of optimizer settings specific to NBA
        """
        return {
            "use_mip_solver": True,
            "enable_random_strategy": True
        }
