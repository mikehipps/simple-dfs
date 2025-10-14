#!/usr/bin/env python3
"""
NFL Team Defensive Statistics by Week Script
Fetches team defensive statistics for week 6 of the current NFL season
and saves them as a CSV file.

Requirements:
- nflreadpy module (https://github.com/nflverse/nflreadpy)
- Virtual environment activation: . venv/bin/activate

Usage:
    . venv/bin/activate && python outcomes/nfl_team_defensive_stats_by_week.py

Key Defensive Stats Available:
- Sacks (def_sacks)
- Interceptions (def_interceptions) 
- Fumbles Forced (def_fumbles_forced)
- Fumble Recoveries (fumble_recovery_opp)
- Defensive TDs (def_tds)
- Safeties (def_safeties)
- Points Allowed (calculated from schedule data)
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
        logging.FileHandler('nfl_team_defensive_stats.log')
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

def fetch_team_defensive_stats(season, week):
    """
    Fetch team defensive statistics for the specified season and week.
    
    Args:
        season (int): NFL season year
        week (int): Week number
    
    Returns:
        pandas.DataFrame: Team defensive statistics data with points allowed
    """
    try:
        import nflreadpy
        
        logger.info(f"Fetching team defensive stats for season {season}, week {week}...")
        
        # Load team stats and schedules
        team_stats = nflreadpy.load_team_stats(seasons=season)
        schedules = nflreadpy.load_schedules(seasons=season)
        
        # Filter for the specific week
        week_team_stats = team_stats.filter(team_stats['week'] == week)
        week_schedule = schedules.filter(schedules['week'] == week)
        
        # Key defensive statistics to extract
        defensive_stats = [
            'def_sacks', 'def_interceptions', 'def_fumbles_forced',
            'fumble_recovery_opp', 'def_tds', 'def_safeties'
        ]
        
        # Calculate points allowed from schedule data
        points_allowed = {}
        for game in week_schedule.to_pandas().itertuples():
            # Home team allowed away team's score
            points_allowed[game.home_team] = game.away_score
            # Away team allowed home team's score  
            points_allowed[game.away_team] = game.home_score
        
        # Select defensive stats and add points allowed
        defensive_data = week_team_stats.select(['team', 'opponent_team'] + defensive_stats).to_pandas()
        defensive_data['points_allowed'] = defensive_data['team'].map(points_allowed)
        
        # Add week and season columns for clarity
        defensive_data['season'] = season
        defensive_data['week'] = week
        
        logger.info(f"Successfully fetched defensive stats for {len(defensive_data)} teams")
        return defensive_data
        
    except Exception as e:
        logger.error(f"Error fetching team defensive stats: {e}")
        raise

def process_defensive_data(defensive_data):
    """
    Process and clean the team defensive statistics data.
    
    Args:
        defensive_data (pandas.DataFrame): Raw team defensive statistics data
    
    Returns:
        pandas.DataFrame: Processed and cleaned data
    """
    logger.info("Processing team defensive data...")
    
    # Basic data cleaning
    # Remove any completely empty rows
    processed_data = defensive_data.dropna(how='all')
    
    # Fill numeric columns with 0 instead of NaN for better CSV output
    numeric_columns = processed_data.select_dtypes(include=['number']).columns
    processed_data[numeric_columns] = processed_data[numeric_columns].fillna(0)
    
    # Fill string columns with empty string
    string_columns = processed_data.select_dtypes(include=['object']).columns
    processed_data[string_columns] = processed_data[string_columns].fillna('')
    
    # Reorder columns for better readability
    column_order = ['season', 'week', 'team', 'opponent_team', 'points_allowed'] + \
                  [col for col in processed_data.columns if col not in ['season', 'week', 'team', 'opponent_team', 'points_allowed']]
    processed_data = processed_data[column_order]
    
    logger.info(f"Processed data shape: {processed_data.shape}")
    return processed_data

def export_to_csv(data, output_path):
    """
    Export the processed data to CSV file.
    
    Args:
        data (pandas.DataFrame): Processed team defensive statistics data
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
        print(f"  - Teams: {len(data)}")
        print(f"  - Columns: {len(data.columns)}")
        print(f"  - File size: {os.path.getsize(output_path) / 1024:.2f} KB")
        
        # Show first few columns for verification
        print(f"  - Sample columns: {list(data.columns[:6])}...")
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        raise

def main():
    """Main function to execute the script."""
    logger.info("Starting NFL Team Defensive Stats by Week script")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    try:
        # Get current season and week
        season, week = get_current_season_and_week()
        
        # Fetch team defensive statistics
        defensive_data = fetch_team_defensive_stats(season, week)
        
        if defensive_data is None or len(defensive_data) == 0:
            logger.warning("No team defensive statistics data found")
            return
        
        # Process the data
        processed_data = process_defensive_data(defensive_data)
        
        # Define output path
        output_path = os.path.join('outcomes', 'nfl-week6-team-defensive-stats.csv')
        
        # Export to CSV
        export_to_csv(processed_data, output_path)
        
        logger.info("Script completed successfully")
        
        # Print sample of the data
        print(f"\nSample of exported defensive data:")
        print(processed_data.head(5).to_string(index=False))
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()