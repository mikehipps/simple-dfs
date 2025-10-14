#!/usr/bin/env python3
"""
NFL Player Stats by Week Script
Fetches all player statistics for week 6 of the current NFL season
and saves them as a CSV file.

Requirements:
- nflreadpy module (https://github.com/nflverse/nflreadpy)
- Virtual environment activation: . venv/bin/activate

Usage:
    . venv/bin/activate && python outcomes/nfl_player_stats_by_week.py
"""

import os
import sys
import logging
from datetime import datetime
import pandas as pd
import polars as pl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('nfl_stats_script.log')
    ]
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import nflreadpy
        logger.info("nflreadpy module is available")
        return True
    except ImportError as e:
        logger.error(f"nflreadpy module not found: {e}")
        logger.info("Please install nflreadpy: pip install nflreadpy")
        return False

def get_current_season_and_week():
    """
    Determine the current NFL season and week 6.
    Uses current date to determine the season and sets week to 6.
    """
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    
    # NFL season typically starts in September
    # If current month is before September, use previous year's season
    if current_month < 9:
        season = current_year - 1
    else:
        season = current_year
    
    week = 6  # Fixed to week 6 as requested
    
    logger.info(f"Using season: {season}, week: {week}")
    return season, week

def fetch_player_stats(season, week):
    """
    Fetch player statistics for the specified season and week.
    
    Args:
        season (int): NFL season year
        week (int): Week number
    
    Returns:
        pandas.DataFrame: Player statistics data
    """
    try:
        import nflreadpy
        
        logger.info(f"Fetching player stats for season {season}, week {week}...")
        
        # Use nflreadpy to get player stats
        # Load player stats with weekly summary level
        player_stats = nflreadpy.load_player_stats(seasons=season, summary_level='week')
        
        # Filter for the specific week
        player_stats = player_stats.filter(player_stats['week'] == week)
        
        logger.info(f"Successfully fetched {len(player_stats)} player records")
        return player_stats
        
    except Exception as e:
        logger.error(f"Error fetching player stats: {e}")
        raise

def process_player_data(player_stats):
    """
    Process and clean the player statistics data.
    
    Args:
        player_stats (polars.DataFrame): Raw player statistics data
    
    Returns:
        pandas.DataFrame: Processed and cleaned data
    """
    logger.info("Processing player data...")
    
    # Convert from Polars to pandas for easier CSV export
    processed_data = player_stats.to_pandas()
    
    # Basic data cleaning
    # Remove any completely empty rows
    processed_data = processed_data.dropna(how='all')
    
    # Fill numeric columns with 0 instead of NaN for better CSV output
    numeric_columns = processed_data.select_dtypes(include=['number']).columns
    processed_data[numeric_columns] = processed_data[numeric_columns].fillna(0)
    
    # Fill string columns with empty string
    string_columns = processed_data.select_dtypes(include=['object']).columns
    processed_data[string_columns] = processed_data[string_columns].fillna('')
    
    logger.info(f"Processed data shape: {processed_data.shape}")
    return processed_data

def export_to_csv(data, output_path):
    """
    Export the processed data to CSV file.
    
    Args:
        data (pandas.DataFrame): Processed player statistics data
        output_path (str): Path to save the CSV file
    """
    try:
        logger.info(f"Exporting data to {output_path}...")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Export to CSV
        data.to_csv(output_path, index=False)
        
        logger.info(f"Successfully exported {len(data)} records to {output_path}")
        
        # Print some basic info about the exported data
        print(f"\nCSV Export Summary:")
        print(f"  - File: {output_path}")
        print(f"  - Records: {len(data):,}")
        print(f"  - Columns: {len(data.columns)}")
        print(f"  - File size: {os.path.getsize(output_path) / 1024:.2f} KB")
        
        # Show first few columns for verification
        print(f"  - Sample columns: {list(data.columns[:5])}...")
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        raise

def main():
    """Main function to execute the script."""
    logger.info("Starting NFL Player Stats by Week script")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    try:
        # Get current season and week
        season, week = get_current_season_and_week()
        
        # Fetch player statistics
        player_stats = fetch_player_stats(season, week)
        
        if player_stats is None or len(player_stats) == 0:
            logger.warning("No player statistics data found")
            return
        
        # Process the data
        processed_data = process_player_data(player_stats)
        
        # Define output path
        output_path = os.path.join('outcomes', 'nfl-week6-player-stats.csv')
        
        # Export to CSV
        export_to_csv(processed_data, output_path)
        
        logger.info("Script completed successfully")
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()