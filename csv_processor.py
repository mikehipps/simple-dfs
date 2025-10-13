#!/usr/bin/env python3
"""
CSV Processor Module for NFL Lineup Generator

This module handles all CSV processing, sanitization, and format conversion
for the NFL lineup generator. It expects standardized column names from the
CSV Match tool and ensures compatibility with pydfs-lineup-optimizer's
expected FanDuel NFL format.

Standardized Column Names:
- Id, Position, First Name, Last Name, FPPG, Game, Team, Opponent, Salary, Injury Indicator

Key Features:
- CSV file reading and validation
- Standardized column processing
- Integration with sanitization functions
- FanDuel NFL format conversion
- Error handling and logging
"""

import os
import sys
import logging
import pandas as pd
from typing import Tuple, Dict, Any

# Import sanitization functions
from sanitization import (
    sanitize_player_id, sanitize_position, sanitize_salary,
    sanitize_fppg, sanitize_random, sanitize_name
)


def preprocess_csv(input_file: str) -> Tuple[str, Dict[str, float]]:
    """
    Preprocess CSV file with robust sanitization for FanDuel NFL format
    
    Expects standardized column names from CSV Match tool:
    ['Id', 'Position', 'First Name', 'Last Name', 'FPPG', 'Game', 'Team', 'Opponent', 'Salary', 'Injury Indicator']
    
    Args:
        input_file (str): Path to input CSV file
        
    Returns:
        tuple: (processed_file_path, random_values_dict)
        
    Raises:
        ValueError: If required columns are missing
        Exception: For any other processing errors
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting CSV preprocessing with sanitization for: {input_file}")
    
    try:
        # Read the original CSV
        df = pd.read_csv(input_file)
        logger.info(f"Original CSV shape: {df.shape}")
        logger.info(f"Original columns: {list(df.columns)}")
        
        # Check for required columns with standardized names
        required_columns = ['Id', 'Position', 'First Name', 'Last Name', 'FPPG', 'Team', 'Opponent', 'Salary', 'Injury Indicator']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        # Check if Game column exists for game info preservation
        has_game_info = 'Game' in df.columns
        if has_game_info:
            logger.info("Found Game column - will preserve game information for D/ST constraints")
        else:
            logger.warning("Game column not found - game information will be empty")
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Create processed DataFrame with standardized columns
        columns_to_copy = required_columns.copy()
        if has_game_info:
            columns_to_copy.append('Game')
        
        processed_df = df[columns_to_copy].copy()
        
        # Apply sanitization to each column
        logger.info("Applying sanitization to CSV data...")
        
        # Sanitize player IDs
        processed_df['Id'] = processed_df['Id'].apply(sanitize_player_id)
        
        # Sanitize positions
        processed_df['Position'] = processed_df['Position'].apply(sanitize_position)
        
        # Sanitize salaries
        processed_df['Salary'] = processed_df['Salary'].apply(sanitize_salary)
        
        # Sanitize FPPG projections
        processed_df['FPPG'] = processed_df['FPPG'].apply(sanitize_fppg)
        
        # Sanitize teams
        processed_df['Team'] = processed_df['Team'].apply(sanitize_name)
        processed_df['Opponent'] = processed_df['Opponent'].apply(sanitize_name)
        
        # Sanitize names
        processed_df['First Name'] = processed_df['First Name'].apply(sanitize_name)
        processed_df['Last Name'] = processed_df['Last Name'].apply(sanitize_name)
        
        # Check for Random column and create dictionary for strategy
        random_values_dict = {}
        if 'Random' in df.columns:
            for _, row in df.iterrows():
                player_id = str(row['Id'])
                random_value = sanitize_random(row['Random'])
                if pd.notna(random_value):
                    random_values_dict[player_id] = random_value
            logger.info(f"Created sanitized random values dictionary with {len(random_values_dict)} players")
        else:
            logger.info("No Random column found - skipping random values processing")
        
        # Add empty Game column if no game info available
        if not has_game_info:
            processed_df['Game'] = ''
            logger.warning("No game information available - using empty strings")
        
        # Ensure all required columns are present in the correct order
        fanduel_columns = ['Id', 'Position', 'First Name', 'Last Name', 'FPPG', 'Game', 'Team', 'Opponent', 'Salary', 'Injury Indicator']
        processed_df = processed_df[fanduel_columns]
        
        # Save processed CSV
        processed_file = 'processed_lineup_data.csv'
        processed_df.to_csv(processed_file, index=False)
        
        logger.info(f"Sanitized CSV saved as: {processed_file}")
        logger.info(f"Sanitized CSV shape: {processed_df.shape}")
        logger.info(f"Sanitized columns: {list(processed_df.columns)}")
        
        # Log sanitization summary
        logger.info("Sanitization summary:")
        logger.info(f"  - Player IDs: {len(processed_df['Id'])} entries sanitized")
        logger.info(f"  - Positions: {processed_df['Position'].nunique()} unique positions standardized")
        logger.info(f"  - Salaries: {len(processed_df['Salary'])} entries converted to integers")
        logger.info(f"  - FPPG: {len(processed_df['FPPG'])} entries converted to floats")
        logger.info(f"  - Random values: {len(random_values_dict)} entries converted to 0-1 range")
        
        return processed_file, random_values_dict
        
    except Exception as e:
        logger.error(f"Error preprocessing CSV: {str(e)}")
        raise


def validate_csv_file(file_path: str) -> bool:
    """
    Validate that a CSV file exists and is readable
    
    Args:
        file_path (str): Path to CSV file
        
    Returns:
        bool: True if file is valid, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(file_path):
        logger.error(f"CSV file not found: {file_path}")
        return False
    
    try:
        # Try to read the file to validate it's a proper CSV
        df = pd.read_csv(file_path)
        logger.info(f"CSV file validated: {file_path} ({len(df)} rows, {len(df.columns)} columns)")
        return True
    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {str(e)}")
        return False


def get_csv_columns(file_path: str) -> list:
    """
    Get the column names from a CSV file
    
    Args:
        file_path (str): Path to CSV file
        
    Returns:
        list: List of column names, or empty list if error
    """
    logger = logging.getLogger(__name__)
    
    try:
        df = pd.read_csv(file_path)
        columns = list(df.columns)
        logger.info(f"CSV columns for {file_path}: {columns}")
        return columns
    except Exception as e:
        logger.error(f"Error getting columns from {file_path}: {str(e)}")
        return []


def cleanup_processed_files():
    """
    Clean up temporary processed files
    
    This function can be called to remove temporary files created during processing
    """
    logger = logging.getLogger(__name__)
    
    processed_file = 'processed_lineup_data.csv'
    if os.path.exists(processed_file):
        try:
            os.remove(processed_file)
            logger.info(f"Cleaned up temporary file: {processed_file}")
        except Exception as e:
            logger.warning(f"Could not remove temporary file {processed_file}: {str(e)}")


if __name__ == "__main__":
    # Test the CSV processor
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("CSV Processor Module Test")
    print("=" * 40)
    
    # Test file validation
    test_file = "test_input.csv"
    if os.path.exists(test_file):
        print(f"Testing CSV validation for {test_file}")
        if validate_csv_file(test_file):
            columns = get_csv_columns(test_file)
            print(f"Columns found: {columns}")
    else:
        print(f"Test file {test_file} not found - skipping validation test")
    
    print("CSV Processor module loaded successfully")