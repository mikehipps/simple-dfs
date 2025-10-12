"""
Configuration file for NFL Lineup Generator
Contains all configurable parameters for the lineup generation process

STRATEGY SELECTION LOGIC:
- If PROGRESSIVE_FACTOR > 0: Use ProgressiveFantasyPointsStrategy only
- If PROGRESSIVE_FACTOR = 0: Use RandomFantasyPointsStrategy only
- Never use both strategies simultaneously
"""

# Lineup Generation Configuration
TOTAL_LINEUPS = 160
NUM_WORKERS = 8
LINEUPS_PER_BATCH = 10

# Optimization Constraints
MAX_EXPOSURE = 0.2
MAX_REPEATING_PLAYERS = 2
MIN_SALARY = 59500

# Strategy Configuration
PROGRESSIVE_FACTOR = 0.0
RANDOM_FACTOR = 2.0

# File Configuration
CSV_FILE = "NFL6-NEW.csv"