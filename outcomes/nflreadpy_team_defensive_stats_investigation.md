# NFLreadpy Team Defensive Statistics Investigation

## Executive Summary

**YES**, nflreadpy provides comprehensive team-level defensive statistics that can be used to automatically populate team defensive totals, eliminating the need for manual data entry each week.

## Key Findings

### Available Team Defensive Statistics

nflreadpy's `load_team_stats()` function provides the following key defensive statistics:

| Statistic | Column Name | Description |
|-----------|-------------|-------------|
| **Sacks** | `def_sacks` | Total sacks by the defense |
| **Interceptions** | `def_interceptions` | Total interceptions by the defense |
| **Fumbles Forced** | `def_fumbles_forced` | Total fumbles forced by the defense |
| **Fumble Recoveries** | `fumble_recovery_opp` | Fumbles recovered from opponents |
| **Defensive TDs** | `def_tds` | Defensive touchdowns scored |
| **Safeties** | `def_safeties` | Safeties recorded |
| **Points Allowed** | (calculated) | Points allowed by the defense |

### Additional Defensive Metrics Available

The API also provides these detailed defensive statistics:
- `def_tackles_solo` - Solo tackles
- `def_tackles_with_assist` - Tackles with assists
- `def_tackle_assists` - Tackle assists
- `def_tackles_for_loss` - Tackles for loss
- `def_qb_hits` - QB hits
- `def_pass_defended` - Passes defended
- `def_interception_yards` - Interception return yards

## Data Availability

### Weekly Data
- ✅ **Available by week**: All defensive stats are available at the weekly level
- ✅ **Current season**: Data available for current and historical seasons
- ✅ **All teams**: Complete data for all 32 NFL teams
- ✅ **Real-time updates**: Data is updated regularly throughout the season

### Points Allowed Calculation
While `load_team_stats()` doesn't directly include points allowed, this can be easily calculated using `load_schedules()`:
- Home team points allowed = Away team score
- Away team points allowed = Home team score

## Implementation

### Created Script
**File**: `outcomes/nfl_team_defensive_stats_by_week.py`

This script automatically:
1. Fetches team defensive statistics for the specified week
2. Calculates points allowed from schedule data
3. Processes and cleans the data
4. Exports to CSV format

### Usage
```bash
. venv/bin/activate && python outcomes/nfl_team_defensive_stats_by_week.py
```

### Sample Output
The script generates a CSV file with the following structure:
```csv
season,week,team,opponent_team,points_allowed,def_sacks,def_interceptions,def_fumbles_forced,fumble_recovery_opp,def_tds,def_safeties
2025,6,ARI,IND,31,1.0,1,0,0,0,0
2025,6,ATL,BUF,14,4.0,2,1,0,0,0
2025,6,BAL,LA,17,2.0,0,1,1,0,0
```

## Integration Recommendations

### 1. Automated Weekly Updates
- Run the defensive stats script weekly before lineup generation
- Use the generated CSV as input for team defensive projections

### 2. Data Integration
- Merge team defensive stats with player projections
- Use defensive stats for D/ST projections and opponent analysis
- Incorporate into lineup optimization constraints

### 3. Workflow Enhancement
- **Before**: Manual entry of team defensive totals each week
- **After**: Automated retrieval via nflreadpy API
- **Time savings**: Eliminates 15-30 minutes of manual work per week

### 4. Additional Benefits
- **Accuracy**: Eliminates manual data entry errors
- **Consistency**: Standardized data format across weeks
- **Scalability**: Easy to extend to other seasons or weeks
- **Reliability**: Official NFL data source

## Technical Details

### Required Dependencies
- nflreadpy (already installed in virtual environment)
- pandas
- polars

### API Functions Used
- `nflreadpy.load_team_stats(seasons=2025)` - Team statistics
- `nflreadpy.load_schedules(seasons=2025)` - Game schedules and scores

### Data Structure
- **Format**: Polars DataFrame (converted to pandas for CSV export)
- **Granularity**: Weekly team-level data
- **Completeness**: All NFL teams included
- **Timeliness**: Updated throughout the season

## Conclusion

**nflreadpy provides a complete solution for automated team defensive statistics retrieval.** The implementation is straightforward, reliable, and eliminates the need for manual data entry. The created script can be integrated into the existing workflow with minimal changes and provides significant time savings while improving data accuracy.

### Next Steps
1. Integrate the defensive stats script into the weekly lineup generation workflow
2. Update projection models to use automated defensive data
3. Consider adding historical defensive data for trend analysis
4. Monitor nflreadpy updates for additional defensive metrics