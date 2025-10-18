"""
Base Sport Helper Interface

Defines the standardized interface for all sport-specific helper classes.
Each sport helper implements methods for constraints, budget, validation, and configuration.
"""

from abc import ABC, abstractmethod
from pydfs_lineup_optimizer import get_optimizer


class SportHelper(ABC):
    """
    Abstract base class for sport-specific helper implementations.
    
    This class defines the standardized interface that all sport helpers must implement
    to provide sport-specific constraints, budgets, and configurations.
    """
    
    @abstractmethod
    def apply_constraints(self, optimizer):
        """
        Apply sport-specific constraints to the optimizer.
        
        Args:
            optimizer: The pydfs-lineup-optimizer instance to apply constraints to
            
        Returns:
            None
        """
        pass
    
    @abstractmethod
    def get_budget(self):
        """
        Get the sport-specific budget constraint.
        
        Returns:
            int: The budget amount for this sport
        """
        pass
    
    @abstractmethod
    def validate_config(self, config):
        """
        Validate sport-specific configuration.
        
        Args:
            config (dict): Configuration dictionary to validate
            
        Returns:
            tuple: (is_valid, error_message)
                - is_valid (bool): True if configuration is valid
                - error_message (str): Error message if invalid, empty string if valid
        """
        pass
    
    @abstractmethod
    def get_sport_specific_config(self):
        """
        Get sport-specific configuration parameters.
        
        Returns:
            dict: Dictionary containing sport-specific configuration parameters
        """
        pass
    
    def get_min_salary_offset(self):
        """
        Get the minimum salary offset percentage for this sport.
        
        This can be overridden by sport-specific implementations if needed.
        
        Returns:
            float: Minimum salary offset as a decimal (e.g., 0.05 for 5% offset)
        """
        return 0.05  # Default 5% offset
    
    def get_optimizer_settings(self):
        """
        Get sport-specific optimizer settings.
        
        Returns:
            dict: Dictionary of optimizer settings specific to this sport
        """
        return {}
    
    def pre_optimization_setup(self, optimizer):
        """
        Perform any sport-specific setup before optimization begins.
        
        Args:
            optimizer: The pydfs-lineup-optimizer instance
            
        Returns:
            None
        """
        pass
    
    def load_metadata(self, csv_path):
        """Load sport-specific metadata from the projections CSV (optional)."""
        return

    def apply_random_bias(self, optimizer, rng):
        """Adjust player projections before each optimization batch (optional)."""
        return
    
    def post_optimization_processing(self, lineups):
        """
        Perform any sport-specific processing after optimization completes.
        
        Args:
            lineups (list): List of generated lineups
            
        Returns:
            list: Processed lineups (can be the same as input if no processing needed)
        """
        return lineups
