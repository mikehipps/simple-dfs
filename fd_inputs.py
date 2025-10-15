"""
Configuration file for Sports-Agnostic FanDuel Lineup Generator
Contains all configurable parameters for the lineup generation process
"""

# Lineup Generation Configuration
TOTAL_LINEUPS = 10000
NUM_WORKERS = 8
LINEUPS_PER_BATCH = 25

# Optimization Constraints
MAX_EXPOSURE = .3
MAX_REPEATING_PLAYERS = 4
MIN_SALARY = 54400

# Random Fantasy Points Strategy Configuration
ENABLE_RANDOM = True        # When True, uses RandomFantasyPointsStrategy with Min/Max Deviation columns from CSV
                            # When False, uses standard projection-based optimization
                            
# File Configuration
CSV_FILE = "projections-csv/nhl1015.csv"   
SPORT_TYPE = "HOCKEY" 
OUTPUT_PREFIX = "fd-lineups"