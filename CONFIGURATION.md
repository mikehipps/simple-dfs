# NFL Lineup Generator Configuration System

This document explains the configuration system for the NFL Lineup Generator.

## Overview

The lineup generator now uses an external configuration system to make it easy to modify parameters without editing the main script. The system consists of two files:

- `inputs_template.py` - Template file tracked in version control
- `inputs.py` - Actual configuration file (not tracked in Git)

## Setup Instructions

1. **First-time setup:**
   ```bash
   cp inputs_template.py inputs.py
   ```

2. **Modify configuration:**
   Edit `inputs.py` with your desired values

3. **Run the generator:**
   ```bash
   python generate_nfl_lineups.py
   ```

## Configuration Parameters

### Lineup Generation Configuration
- `TOTAL_LINEUPS` (int): Total number of lineups to generate (default: 5000)
- `NUM_WORKERS` (int): Number of parallel worker threads (default: 8)
- `LINEUPS_PER_BATCH` (int): Number of lineups generated per batch (default: 25)

### Optimization Constraints
- `MAX_EXPOSURE` (float): Maximum player exposure percentage (0.0-1.0, default: 0.25)
- `MAX_REPEATING_PLAYERS` (int): Maximum number of repeating players across lineups (default: 3)
- `MIN_SALARY` (int): Minimum salary cap usage (default: 59500)

### Strategy Configuration
- `PROGRESSIVE_FACTOR` (float): Controls which fantasy points strategy to use:
  - **PROGRESSIVE_FACTOR > 0**: Use ProgressiveFantasyPointsStrategy only (default: 0.02)
  - **PROGRESSIVE_FACTOR = 0**: Use RandomFantasyPointsStrategy only
  - **Never use both strategies simultaneously**

### File Configuration
- `CSV_FILE` (str): Input CSV file name (default: "NFL6-CLEAN2.csv")

## Git Integration

- `inputs_template.py` is tracked in version control
- `inputs.py` is ignored via `.gitignore` to prevent accidental commits of personal configurations
- Always use the template as a starting point for new configurations

## Strategy Selection Examples

### Progressive Strategy (Recommended)
```python
# Use ProgressiveFantasyPointsStrategy with 2% progressive scaling
PROGRESSIVE_FACTOR = 0.02
```

### Random Strategy
```python
# Use RandomFantasyPointsStrategy only
PROGRESSIVE_FACTOR = 0.0
```

## Example Configuration

```python
# For faster generation with fewer lineups
TOTAL_LINEUPS = 1000
NUM_WORKERS = 4
LINEUPS_PER_BATCH = 50

# For more diverse lineups
MAX_EXPOSURE = 0.15
MAX_REPEATING_PLAYERS = 2

# Use Progressive strategy
PROGRESSIVE_FACTOR = 0.02

# For different input file
CSV_FILE = "my-custom-data.csv"
```

## Troubleshooting

If you see the error "Configuration file 'inputs.py' not found", run:
```bash
cp inputs_template.py inputs.py
```

Then edit `inputs.py` with your desired configuration values.