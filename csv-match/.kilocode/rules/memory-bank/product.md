# CSV Match - Product Description

## Why This Project Exists
CSV Match solves the critical data integration challenge faced by fantasy sports players and analysts who need to combine player data from multiple sources. Different data providers use varying naming conventions, abbreviations, and team references, making manual data merging time-consuming and error-prone.

## Core Problems Solved
1. **Name Inconsistency**: "Mike" vs "Michael", "AJ" vs "A.J.", "Chris" vs "Christopher"
2. **Team Reference Variations**: "LA Rams" vs "Los Angeles Rams" vs "LAR"
3. **Defense/Special Teams Handling**: "Baltimore D/ST" vs "Baltimore Ravens Defense"
4. **Multi-Source Data Integration**: Combining projections, salaries, and ownership data

## How It Works - User Experience
1. **Upload Phase**: Users upload two CSV files containing player data
2. **Configuration Phase**: 
   - Select sport (NFL, MLB, NBA, NHL)
   - Choose primary file for matching
   - Configure name columns (single field or composed from multiple columns)
   - Select team columns
   - Choose which columns to keep from each file
3. **Matching Phase**:
   - Automatic normalization of names and teams
   - Fuzzy matching within same teams
   - Interactive review for ambiguous matches
4. **Export Phase**: Download merged CSV and matching manifest

## User Experience Goals
- **Zero Installation**: Pure browser-based solution
- **Intuitive Workflow**: Step-by-step process matching user mental model
- **Immediate Feedback**: Real-time matching results and review interface
- **Persistent Learning**: Browser-local alias storage improves over time
- **Professional Output**: Clean merged data with proper column prefixes

## Key User Scenarios
1. **DFS Player**: Combine salary data from one source with projections from another
2. **Sports Analyst**: Merge historical performance data with current season statistics
3. **Fantasy Manager**: Combine waiver wire data with team roster information
4. **Data Scientist**: Prepare clean datasets for machine learning models

## Success Metrics
- High percentage of automatic matches (reduces manual review)
- Low false positive rate in fuzzy matching
- User retention through alias persistence
- Export quality enabling direct analysis use