"""
NFL Sport Helper

NFL-specific helper implementation with D/ST vs opposing QB/RB constraints
and NFL-specific budget and configuration settings.
"""

import logging
from sport_helpers.base import SportHelper


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
        return 0.05  # 5% offset for NFL
    
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