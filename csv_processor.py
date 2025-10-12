#!/usr/bin/env python3
"""
CSV Processor Module for NFL Lineup Generator

This module handles all CSV processing, sanitization, and format conversion
for the NFL lineup generator. It provides robust preprocessing functions
that handle various CSV input formats and ensure compatibility with
pydfs-lineup-optimizer's expected formats.

Key Features:
- CSV file reading and validation
- Column mapping and standardization
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
        
        # Check for required columns with exact matching
        required_columns = ['B_Id', 'B_Position', 'B_Nickname', 'B_Salary', 'A_ppg_projection', 'B_Team', 'B_Opponent', 'Random']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Create processed DataFrame with exact column mapping
        processed_df = df[required_columns].copy()
        
        # Apply sanitization to each column
        logger.info("Applying sanitization to CSV data...")
        
        # Sanitize player IDs
        processed_df['B_Id'] = processed_df['B_Id'].apply(sanitize_player_id)
        
        # Sanitize positions
        processed_df['B_Position'] = processed_df['B_Position'].apply(sanitize_position)
        
        # Sanitize salaries
        processed_df['B_Salary'] = processed_df['B_Salary'].apply(sanitize_salary)
        
        # Sanitize FPPG projections
        processed_df['A_ppg_projection'] = processed_df['A_ppg_projection'].apply(sanitize_fppg)
        
        # Sanitize teams
        processed_df['B_Team'] = processed_df['B_Team'].apply(sanitize_name)
        processed_df['B_Opponent'] = processed_df['B_Opponent'].apply(sanitize_name)
        
        # Sanitize random values and create dictionary for strategy
        random_values_dict = {}
        for _, row in processed_df.iterrows():
            player_id = str(row['B_Id'])
            random_value = sanitize_random(row['Random'])
            if pd.notna(random_value):
                random_values_dict[player_id] = random_value
        
        logger.info(f"Created sanitized random values dictionary with {len(random_values_dict)} players")
        
        # Apply standard column mapping for FanDuel
        standard_mapping = {
            'B_Id': 'Id',
            'B_Position': 'Position',
            'B_Nickname': 'Nickname',
            'B_Salary': 'Salary',
            'A_ppg_projection': 'FPPG',
            'B_Team': 'Team',
            'B_Opponent': 'Opponent'
        }
        
        processed_df = processed_df.rename(columns=standard_mapping)
        
        # Split nickname into First Name and Last Name for FanDuel format
        processed_df['First Name'] = processed_df['Nickname'].apply(
            lambda x: x.split()[0] if pd.notna(x) else ''
        )
        processed_df['Last Name'] = processed_df['Nickname'].apply(
            lambda x: ' '.join(x.split()[1:]) if pd.notna(x) and len(x.split()) > 1 else ''
        )
        
        # Add required columns for FanDuel NFL
        processed_df['Injury Indicator'] = ''  # Empty injury indicator
        processed_df['Game'] = ''  # Empty game info
        
        # Reorder columns to match FanDuel expected format
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