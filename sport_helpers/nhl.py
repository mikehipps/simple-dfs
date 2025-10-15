"""
NHL Sport Helper

NHL-specific helper implementation (stub for now).
Will be implemented in future phases.
"""

import logging
from sport_helpers.base import SportHelper


class NHLHelper(SportHelper):
    """
    NHL-specific helper implementation (stub).
    
    This is a placeholder for future NHL-specific constraints and configurations.
    """
    
    def __init__(self):
        """Initialize NHL helper with default configuration."""
        self.logger = logging.getLogger(__name__)
    
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