#!/usr/bin/env python3
"""
Player Usage Analysis Script
Analyzes NFL Week 6 FanDuel lineups to generate player usage report
Supports new folder structure and naming conventions for 5000 lineups
"""

import csv
import sys
import os
import glob
from collections import defaultdict
from typing import Dict, List, Tuple


def read_lineups_csv(file_path: str) -> List[List[str]]:
    """
    Read the lineups CSV file and return the data
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        List of lineups (each lineup is a list of player strings)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            data = list(reader)
        return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)


def parse_player_info(player_string: str) -> Tuple[str, str]:
    """
    Parse player string to extract name and position
    
    Args:
        player_string: String in format "PlayerName(ID-ID)"
        
    Returns:
        Tuple of (player_name, position)
    """
    # Extract player name (everything before the first parenthesis)
    if '(' in player_string:
        name = player_string.split('(')[0].strip()
    else:
        name = player_string.strip()
    
    # Determine position based on the column (we'll handle this in the main function)
    return name


def analyze_player_usage(lineups_data: List[List[str]]) -> Dict[str, Dict[str, int]]:
    """
    Analyze player usage across all lineups
    
    Args:
        lineups_data: List of lineups from CSV
        
    Returns:
        Dictionary with player names as keys and usage info as values
    """
    # Define positions based on column headers
    positions = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DEF']
    
    # Dictionary to store player usage
    player_usage = defaultdict(lambda: {'count': 0, 'positions': set()})
    
    # Skip header row
    for row_num, lineup in enumerate(lineups_data[1:], start=2):
        for col_num, player_string in enumerate(lineup[:9]):  # Only process first 9 columns (player positions)
            if player_string:  # Skip empty cells
                player_name = parse_player_info(player_string)
                position = positions[col_num]
                
                player_usage[player_name]['count'] += 1
                player_usage[player_name]['positions'].add(position)
    
    return player_usage


def generate_report(player_usage: Dict[str, Dict[str, int]], total_lineups: int) -> List[Tuple[str, str, int, float]]:
    """
    Generate sorted report with player usage statistics
    
    Args:
        player_usage: Dictionary with player usage data
        total_lineups: Total number of lineups analyzed
        
    Returns:
        List of tuples (player_name, positions, count, percentage) sorted by count
    """
    report_data = []
    
    for player, data in player_usage.items():
        count = data['count']
        positions = ', '.join(sorted(data['positions']))
        percentage = (count / total_lineups) * 100
        
        report_data.append((player, positions, count, percentage))
    
    # Sort by usage count (highest to lowest)
    report_data.sort(key=lambda x: x[2], reverse=True)
    
    return report_data


def save_report_to_csv(report_data: List[Tuple[str, str, int, float]], output_file: str):
    """
    Save the report to a CSV file
    
    Args:
        report_data: List of report data tuples
        output_file: Path to output CSV file
    """
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Write header
            writer.writerow(['Player Name', 'Positions', 'Times Used', 'Usage Percentage (%)'])
            
            # Write data
            for player, positions, count, percentage in report_data:
                writer.writerow([player, positions, count, f"{percentage:.2f}"])
        
        print(f"Report saved to: {output_file}")
    except Exception as e:
        print(f"Error saving CSV file: {e}")


def display_report_console(report_data: List[Tuple[str, str, int, float]]):
    """
    Display the report in the console with formatted output
    
    Args:
        report_data: List of report data tuples
    """
    print("\n" + "="*80)
    print("PLAYER USAGE REPORT - NFL Week 6 FanDuel Lineups")
    print("="*80)
    print(f"{'Player Name':<25} {'Positions':<15} {'Used':<6} {'Usage %':<8}")
    print("-"*80)
    
    for player, positions, count, percentage in report_data:
        print(f"{player:<25} {positions:<15} {count:<6} {percentage:.2f}%")
    
    print("-"*80)
    print(f"Total players analyzed: {len(report_data)}")
    print("="*80)


def find_latest_lineup_file():
    """
    Find the latest lineup file in the lineups directory
    
    Returns:
        str: Path to the latest lineup file
    """
    lineups_dir = "lineups"
    
    # Check if lineups directory exists
    if not os.path.exists(lineups_dir):
        print(f"Error: Lineups directory '{lineups_dir}' not found.")
        sys.exit(1)
    
    # Look for lineup files with the new naming convention (including 5000 lineups)
    pattern = os.path.join(lineups_dir, "*-5000-fd-nfl-week6-lineups.csv")
    lineup_files = glob.glob(pattern)
    
    if not lineup_files:
        # Fallback to old pattern if no 5000-lineup files found
        old_pattern = os.path.join(lineups_dir, "*-*-fd-nfl-week6-lineups.csv")
        lineup_files = glob.glob(old_pattern)
        if not lineup_files:
            print(f"Error: No lineup files found matching patterns: {pattern} or {old_pattern}")
            sys.exit(1)
        else:
            print(f"Warning: Using older lineup file pattern. Found {len(lineup_files)} files.")
    
    # Sort by modification time (newest first) and return the latest
    latest_file = max(lineup_files, key=os.path.getmtime)
    return latest_file


def generate_output_filename(input_file):
    """
    Generate output filename based on input lineup filename
    
    Args:
        input_file (str): Path to input lineup file
        
    Returns:
        str: Path to output usage report file
    """
    # Extract the base filename without extension
    base_name = os.path.basename(input_file)
    name_without_ext = os.path.splitext(base_name)[0]
    
    # Replace "lineups" with "player-usage" in the filename
    output_name = name_without_ext.replace("lineups", "player-usage") + ".csv"
    
    # Return path in the same directory
    return os.path.join(os.path.dirname(input_file), output_name)


def main():
    """Main function to run the player usage analysis"""
    print("Starting player usage analysis...")
    
    # Find the latest lineup file
    input_file = find_latest_lineup_file()
    output_file = generate_output_filename(input_file)
    
    print(f"Found lineup file: {input_file}")
    print(f"Output will be saved to: {output_file}")
    
    # Read the lineups data
    print(f"Reading lineups from: {input_file}")
    lineups_data = read_lineups_csv(input_file)
    
    # Calculate total lineups (excluding header)
    total_lineups = len(lineups_data) - 1
    print(f"Analyzing {total_lineups} lineups...")
    
    # Analyze player usage
    player_usage = analyze_player_usage(lineups_data)
    
    # Generate report
    report_data = generate_report(player_usage, total_lineups)
    
    # Save report to CSV
    save_report_to_csv(report_data, output_file)
    
    # Display report in console
    display_report_console(report_data)
    
    # Show top 10 most used players
    print("\nTOP 10 MOST USED PLAYERS:")
    print("-" * 60)
    for i, (player, positions, count, percentage) in enumerate(report_data[:10], 1):
        print(f"{i:2d}. {player:<20} {positions:<12} {count:2d} times ({percentage:.1f}%)")


if __name__ == "__main__":
    main()