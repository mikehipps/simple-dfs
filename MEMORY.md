# Project Memory and Workflow Documentation

## Auto-Commit Workflow

This project implements an automatic staging and committing workflow to ensure regular version control checkpoints during development.

### Files Created

- **`auto_commit.sh`**: Bash script for automatic staging and committing
- **`auto_commit.py`**: Python script with the same functionality, more flexible for integration

### Usage

#### Bash Script
```bash
# Auto-generate commit message based on file types
./auto_commit.sh

# Use custom commit message
./auto_commit.sh "Your custom commit message"
```

#### Python Script
```bash
# Auto-generate commit message based on file types
python auto_commit.py

# Use custom commit message
python auto_commit.py "Your custom commit message"
```

### Features

1. **Automatic Change Detection**: Checks if there are any changes to commit
2. **Smart Commit Messages**: Generates descriptive messages based on file types:
   - `.py` files → "Update: Python code changes"
   - `.md` files → "Update: Documentation" 
   - Frontend files → "Update: Frontend files"
   - Custom messages can be provided
3. **Colored Output**: Clear status indicators for success, warnings, and errors
4. **Commit Verification**: Shows commit summary and file statistics after committing

### Integration with Code Subtasks

For future code subtasks, use the auto-commit workflow at the end of each significant change:

```python
# Example: After completing a code change
import subprocess
subprocess.run(["python", "auto_commit.py", "Description of changes made"])
```

### Benefits

- **Regular Checkpoints**: Creates safe points to revert to if needed
- **Better Version History**: Clear, descriptive commit messages
- **Automated Process**: Reduces manual git operations
- **Consistent Workflow**: Standardized approach across all development tasks

### Current Commit Status

The project has been successfully committed with the message:
**"Revert: Remove fuzzy matching and restore exact column matching"**

This commit includes:
- Configuration documentation updates
- Dynamic queue implementation documentation
- Frontend filter components
- Template files
- Code optimizations

### Virtual Environment Workflow

**Important**: Always activate the virtual environment before running Python commands:

```bash
. venv/bin/activate && python [your_command]
```

This ensures all dependencies (nflreadpy, pandas, etc.) are available.

### NFLreadpy Team Defensive Statistics Investigation Results

**Key Finding**: nflreadpy provides comprehensive team defensive statistics that can automate manual data entry.

**Available Defensive Stats**:
- Sacks (`def_sacks`)
- Interceptions (`def_interceptions`)
- Fumbles forced (`def_fumbles_forced`)
- Fumble recoveries (`fumble_recovery_opp`)
- Defensive TDs (`def_tds`)
- Safeties (`def_safeties`)
- Points allowed (calculated from schedule data)

**Created Script**: `outcomes/nfl_team_defensive_stats_by_week.py`
- Automatically fetches weekly team defensive stats
- Calculates points allowed from schedule data
- Exports to CSV format for integration

**Benefits**:
- Eliminates 15-30 minutes of manual data entry per week
- Improves accuracy and consistency
- Uses official NFL data sources

### Next Steps

1. Use `auto_commit.py` or `auto_commit.sh` after each code subtask
2. Provide descriptive commit messages when making significant changes
3. The scripts will handle staging all changes automatically
4. Review commit history regularly to track progress
5. **Always use**: `. venv/bin/activate && python` for Python commands
6. Integrate team defensive stats script into weekly workflow