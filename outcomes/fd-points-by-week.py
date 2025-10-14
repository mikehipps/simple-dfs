#!/usr/bin/env python3
"""
FanDuel Fantasy Points Calculator by Week
Calculates FanDuel fantasy points for all players and team defenses using the scoring rules provided.

Requirements:
- pandas module
- Input data:
  - Player stats: nfl-week6-player-stats.csv
  - Team defensive stats: nfl-week6-team-defensive-stats.csv

Usage:
    python outcomes/fd-points-by-week.py

Output:
    fd-pts-week6.csv with columns: player_display_name, position, season, week, team, opponent_team, fd_points
    (Includes both individual players and team defenses)
"""

import os
import sys
import logging
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def calculate_fanduel_points(row):
    """
    Calculate FanDuel fantasy points for a player based on their stats.
    
    Args:
        row (pandas.Series): Player statistics row
        
    Returns:
        float: Total FanDuel fantasy points
    """
    fd_points = 0.0
    
    # Get position for conditional logic
    position_value = row.get('position', '')
    if pd.isna(position_value):
        position = ''
    else:
        position = str(position_value).upper()
    
    # OFFENSIVE SCORING
    
    # Receiving stats
    receptions = row.get('receptions', 0)
    receiving_yards = row.get('receiving_yards', 0)
    receiving_tds = row.get('receiving_tds', 0)
    
    # Points per Reception = 0.5 Points
    fd_points += receptions * 0.5
    
    # Receiving Yards = 0.1 Point per Yard
    fd_points += receiving_yards * 0.1
    
    # 100+ Receiving Yard Bonus = 3 Points
    if receiving_yards >= 100:
        fd_points += 3
    
    # Receiving Touchdown = 6 Points
    fd_points += receiving_tds * 6
    
    # Rushing stats
    rushing_yards = row.get('rushing_yards', 0)
    rushing_tds = row.get('rushing_tds', 0)
    
    # Rushing Yards = 0.1 Point per Yard
    fd_points += rushing_yards * 0.1
    
    # 100+ Rushing Yard Bonus = 3 Points
    if rushing_yards >= 100:
        fd_points += 3
    
    # Rushing Touchdown = 6 Points
    fd_points += rushing_tds * 6
    
    # Passing stats
    passing_yards = row.get('passing_yards', 0)
    passing_tds = row.get('passing_tds', 0)
    passing_interceptions = row.get('passing_interceptions', 0)
    
    # Passing Yards = 0.04 Points
    fd_points += passing_yards * 0.04
    
    # 300+ Passing Yard Bonus = 3 Points
    if passing_yards >= 300:
        fd_points += 3
    
    # Passing Touchdown = 4 Points
    fd_points += passing_tds * 4
    
    # Interception Thrown = -1 Points
    fd_points += passing_interceptions * -1
    
    # Two-Point Conversions
    passing_2pt_conversions = row.get('passing_2pt_conversions', 0)
    rushing_2pt_conversions = row.get('rushing_2pt_conversions', 0)
    receiving_2pt_conversions = row.get('receiving_2pt_conversions', 0)
    
    # Two-Point Conversion = 2 Points
    fd_points += (rushing_2pt_conversions + receiving_2pt_conversions) * 2
    
    # Two-Point Conversion Thrown = 2 Points
    fd_points += passing_2pt_conversions * 2
    
    # Fumbles (total fumbles from rushing and receiving)
    rushing_fumbles = row.get('rushing_fumbles', 0)
    receiving_fumbles = row.get('receiving_fumbles', 0)
    sack_fumbles = row.get('sack_fumbles', 0)
    total_fumbles = rushing_fumbles + receiving_fumbles + sack_fumbles
    
    # Fumble = -2 Points (any fumble, regardless of recovery)
    fd_points += total_fumbles * -2
    
    # Special Teams and Return TDs
    special_teams_tds = row.get('special_teams_tds', 0)
    punt_return_yards = row.get('punt_return_yards', 0)
    kickoff_return_yards = row.get('kickoff_return_yards', 0)
    
    # Kickoff Return Touchdown = 6 Points
    # Punt Return Touchdown = 6 Points
    # Note: Using special_teams_tds as proxy for return TDs
    fd_points += special_teams_tds * 6
    
    # Kicking stats
    fg_made_0_19 = row.get('fg_made_0_19', 0)
    fg_made_20_29 = row.get('fg_made_20_29', 0)
    fg_made_30_39 = row.get('fg_made_30_39', 0)
    fg_made_40_49 = row.get('fg_made_40_49', 0)
    fg_made_50_59 = row.get('fg_made_50_59', 0)
    fg_made_60_ = row.get('fg_made_60_', 0)
    
    # 0-39 Yard Field Goal = 3 Points
    fd_points += (fg_made_0_19 + fg_made_20_29 + fg_made_30_39) * 3
    
    # 40-49 Yard Field Goal = 4 Points
    fd_points += fg_made_40_49 * 4
    
    # 50+ Yard Field Goal = 5 Points
    fd_points += (fg_made_50_59 + fg_made_60_) * 5
    
    # Extra-Point Conversions = 1 Point
    pat_made = row.get('pat_made', 0)
    fd_points += pat_made * 1
    
    # DEFENSIVE SCORING (for defensive players)
    if position in ['DE', 'DT', 'LB', 'CB', 'S', 'DB', 'DL']:
        # Sacks = 1pt
        def_sacks = row.get('def_sacks', 0)
        fd_points += def_sacks * 1
        
        # Fumble Recovered = 2 Points
        fumble_recovery_opp = row.get('fumble_recovery_opp', 0)
        fd_points += fumble_recovery_opp * 2
        
        # Interception = 2 Points
        def_interceptions = row.get('def_interceptions', 0)
        fd_points += def_interceptions * 2
        
        # Safety = 2 Points
        def_safeties = row.get('def_safeties', 0)
        fd_points += def_safeties * 2
        
        # Blocked Punt = 2 Points (using blocked field goals as proxy)
        fg_blocked = row.get('fg_blocked', 0)
        pat_blocked = row.get('pat_blocked', 0)
        fd_points += (fg_blocked + pat_blocked) * 2
        
        # Extra-Point Return = 2 Points (using defensive TDs as proxy)
        def_tds = row.get('def_tds', 0)
        fd_points += def_tds * 6  # Defensive TDs are 6 points
    
    # Team Self Fumble Recovery Touchdown = 6 Points
    # Note: This is handled in the defensive scoring above via def_tds
    
    return round(fd_points, 2)

def load_player_stats(input_path):
    """
    Load player statistics from CSV file.
    
    Args:
        input_path (str): Path to input CSV file
        
    Returns:
        pandas.DataFrame: Player statistics data
    """
    try:
        logger.info(f"Loading player stats from {input_path}...")
        df = pd.read_csv(input_path)
        logger.info(f"Successfully loaded {len(df)} player records")
        return df
    except Exception as e:
        logger.error(f"Error loading player stats: {e}")
        raise

def load_team_defensive_stats(input_path):
    """
    Load team defensive statistics from CSV file.
    
    Args:
        input_path (str): Path to input CSV file
        
    Returns:
        pandas.DataFrame: Team defensive statistics data
    """
    try:
        logger.info(f"Loading team defensive stats from {input_path}...")
        df = pd.read_csv(input_path)
        logger.info(f"Successfully loaded {len(df)} team defensive records")
        return df
    except Exception as e:
        logger.error(f"Error loading team defensive stats: {e}")
        raise

def calculate_team_defense_fanduel_points(row):
    """
    Calculate FanDuel fantasy points for a team defense based on defensive stats.
    
    Args:
        row (pandas.Series): Team defensive statistics row
        
    Returns:
        float: Total FanDuel fantasy points for team defense
    """
    fd_points = 0.0
    
    # DEFENSIVE SCORING RULES FOR TEAM DEFENSE
    
    # Sacks = 1pt
    def_sacks = row.get('def_sacks', 0)
    fd_points += def_sacks * 1
    
    # Fumble Recovered = 2 Points
    fumble_recovery_opp = row.get('fumble_recovery_opp', 0)
    fd_points += fumble_recovery_opp * 2
    
    # Interception = 2 Points
    def_interceptions = row.get('def_interceptions', 0)
    fd_points += def_interceptions * 2
    
    # Safety = 2 Points
    def_safeties = row.get('def_safeties', 0)
    fd_points += def_safeties * 2
    
    # Defensive TD = 6 Points
    def_tds = row.get('def_tds', 0)
    fd_points += def_tds * 6
    
    # Points Allowed scoring
    points_allowed = row.get('points_allowed', 0)
    
    if points_allowed == 0:
        # 0 points allowed = 10 points
        fd_points += 10
    elif points_allowed <= 6:
        # 1-6 points allowed = 7 points
        fd_points += 7
    elif points_allowed <= 13:
        # 7-13 points allowed = 4 points
        fd_points += 4
    elif points_allowed <= 20:
        # 14-20 points allowed = 1 point
        fd_points += 1
    elif points_allowed <= 27:
        # 21-27 points allowed = 0 points
        fd_points += 0
    elif points_allowed <= 34:
        # 28-34 points allowed = -1 point
        fd_points += -1
    else:
        # 35+ points allowed = -4 points
        fd_points += -4
    
    return round(fd_points, 2)

def combine_player_and_team_data(player_data, team_defense_data):
    """
    Combine player statistics and team defense data into a single dataset.
    
    Args:
        player_data (pandas.DataFrame): Player statistics with FanDuel points
        team_defense_data (pandas.DataFrame): Team defensive statistics
        
    Returns:
        pandas.DataFrame: Combined dataset with both players and team defenses
    """
    logger.info("Combining player and team defense data...")
    
    # Calculate FanDuel points for team defenses
    team_defense_data['fd_points'] = team_defense_data.apply(calculate_team_defense_fanduel_points, axis=1)
    
    # Prepare team defense data for combination
    # Team defenses need to be represented in the same format as players
    team_defense_combined = team_defense_data.copy()
    
    # Add required columns for team defenses
    team_defense_combined['player_display_name'] = team_defense_combined['team'] + ' D/ST'
    team_defense_combined['position'] = 'DST'
    
    # Ensure all required columns are present
    required_columns = ['player_display_name', 'position', 'season', 'week', 'team', 'opponent_team', 'fd_points']
    
    # Filter player data to required columns
    player_filtered = player_data[required_columns].copy()
    
    # Filter team defense data to required columns
    team_defense_filtered = team_defense_combined[required_columns].copy()
    
    # Combine the datasets
    combined_data = pd.concat([player_filtered, team_defense_filtered], ignore_index=True)
    
    logger.info(f"Combined {len(player_filtered)} players with {len(team_defense_filtered)} team defenses")
    logger.info(f"Total records in combined dataset: {len(combined_data)}")
    
    return combined_data

def calculate_fanduel_points_for_all_players(df):
    """
    Calculate FanDuel points for all players in the dataset.
    
    Args:
        df (pandas.DataFrame): Player statistics data
        
    Returns:
        pandas.DataFrame: Data with FanDuel points added
    """
    logger.info("Calculating FanDuel fantasy points...")
    
    # Calculate FanDuel points for each player
    df['fd_points'] = df.apply(calculate_fanduel_points, axis=1)
    
    logger.info(f"FanDuel points calculated for {len(df)} players")
    logger.info(f"FanDuel points range: {df['fd_points'].min():.2f} to {df['fd_points'].max():.2f}")
    
    return df

def filter_output_columns(df):
    """
    Filter the dataframe to only include required output columns.
    
    Args:
        df (pandas.DataFrame): Full player statistics data
        
    Returns:
        pandas.DataFrame: Filtered data with only required columns
    """
    required_columns = [
        'player_display_name', 
        'position', 
        'season', 
        'week', 
        'team', 
        'opponent_team', 
        'fd_points'
    ]
    
    # Check which required columns exist in the dataframe
    available_columns = [col for col in required_columns if col in df.columns]
    
    # If any required columns are missing, log a warning
    missing_columns = set(required_columns) - set(available_columns)
    if missing_columns:
        logger.warning(f"Missing required columns: {missing_columns}")
    
    # Filter to available required columns
    filtered_df = df[available_columns].copy()
    
    logger.info(f"Filtered to {len(filtered_df.columns)} output columns")
    return filtered_df

def export_to_csv(df, output_path):
    """
    Export the processed data to CSV file.
    
    Args:
        df (pandas.DataFrame): Processed player statistics data
        output_path (str): Path to save the CSV file
    """
    try:
        logger.info(f"Exporting data to {output_path}...")
        
        # Export to CSV
        df.to_csv(output_path, index=False)
        
        logger.info(f"Successfully exported {len(df)} records to {output_path}")
        
        # Print some basic info about the exported data
        print(f"\nCSV Export Summary:")
        print(f"  - File: {output_path}")
        print(f"  - Records: {len(df):,}")
        print(f"  - Columns: {len(df.columns)}")
        print(f"  - FanDuel points range: {df['fd_points'].min():.2f} to {df['fd_points'].max():.2f}")
        
        # Show breakdown by position
        position_counts = df['position'].value_counts()
        print(f"  - Position breakdown:")
        for position, count in position_counts.items():
            print(f"    - {position}: {count} players")
        
        # Show top 5 players by FanDuel points
        top_players = df.nlargest(5, 'fd_points')
        print(f"  - Top 5 players by FanDuel points:")
        for _, player in top_players.iterrows():
            print(f"    - {player['player_display_name']} ({player['position']}): {player['fd_points']:.2f} points")
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        raise

def main():
    """Main function to execute the script."""
    logger.info("Starting FanDuel Fantasy Points Calculator")
    
    try:
        # Define input and output paths
        player_input_path = 'outcomes/nfl-week6-player-stats.csv'
        team_defense_input_path = 'outcomes/nfl-week6-team-defensive-stats.csv'
        output_path = 'outcomes/fd-pts-week6.csv'
        
        # Check if player stats file exists
        if not os.path.exists(player_input_path):
            logger.error(f"Player stats file not found: {player_input_path}")
            logger.info("Please run outcomes/nfl_player_stats_by_week.py first to generate the player stats data")
            sys.exit(1)
        
        # Check if team defense stats file exists
        if not os.path.exists(team_defense_input_path):
            logger.error(f"Team defense stats file not found: {team_defense_input_path}")
            logger.info("Please run outcomes/nfl_team_defensive_stats_by_week.py first to generate the team defense data")
            sys.exit(1)
        
        # Load player statistics
        player_stats = load_player_stats(player_input_path)
        
        if player_stats is None or len(player_stats) == 0:
            logger.warning("No player statistics data found")
            return
        
        # Load team defensive statistics
        team_defense_stats = load_team_defensive_stats(team_defense_input_path)
        
        if team_defense_stats is None or len(team_defense_stats) == 0:
            logger.warning("No team defensive statistics data found")
            return
        
        # Calculate FanDuel points for players
        player_stats_with_points = calculate_fanduel_points_for_all_players(player_stats)
        
        # Combine player and team defense data
        combined_data = combine_player_and_team_data(player_stats_with_points, team_defense_stats)
        
        # Filter to required output columns
        filtered_data = filter_output_columns(combined_data)
        
        # Export to CSV
        export_to_csv(filtered_data, output_path)
        
        logger.info("Script completed successfully")
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()