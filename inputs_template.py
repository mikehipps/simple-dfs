"""
Configuration Template for NFL Lineup Generator
Copy this file to inputs.py and modify the values as needed
This file should be tracked in version control

STRATEGY SELECTION LOGIC:
- If PROGRESSIVE_FACTOR > 0: Use ProgressiveFantasyPointsStrategy only
- If PROGRESSIVE_FACTOR = 0: Use default optimizer strategy (no custom randomization)
- Never use both strategies simultaneously
"""

# Lineup Generation Configuration
TOTAL_LINEUPS = 5000
NUM_WORKERS = 8
LINEUPS_PER_BATCH = 25

# Optimization Constraints
MAX_EXPOSURE = 0.25
MAX_REPEATING_PLAYERS = 3
MIN_SALARY = 59500

# Strategy Configuration
PROGRESSIVE_FACTOR = 0.02  # Set to 0 to use default optimizer strategy, > 0 for ProgressiveFantasyPointsStrategy

# File Configuration
CSV_FILE = "NFL6-CLEAN2.csv"