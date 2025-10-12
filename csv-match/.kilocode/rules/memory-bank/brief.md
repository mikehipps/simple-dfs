# CSV Match - Project Brief

## Project Overview
CSV Match is a browser-based sports data matching tool that enables users to merge two CSV files containing player data from different sources. The application focuses on solving the common problem of inconsistent player naming conventions across different fantasy sports data providers.

## Core Purpose
- **Primary Function**: Match player records between two CSV files using fuzzy name matching and team normalization
- **Key Problem Solved**: Different data sources use varying formats for player names (nicknames, abbreviations, suffixes) and team names
- **Target Users**: Daily fantasy sports players, data analysts, and sports enthusiasts who need to combine data from multiple sources

## Core Features
1. **Multi-Sport Support**: NFL, MLB, NBA, NHL with comprehensive team alias mappings
2. **Name Normalization**: Handles nicknames, suffixes, and special cases like D/ST (Defense/Special Teams)
3. **Flexible Name Composition**: Support for single-column names or composed names from multiple columns
4. **Fuzzy Matching**: Uses Fuse.js for approximate name matching within the same team
5. **Interactive Review**: Manual resolution interface for ambiguous matches
6. **Persistent Aliases**: Browser-local storage for user-defined name mappings
7. **Data Export**: Download merged CSV files and matching manifest

## Technical Foundation
- Pure client-side JavaScript application (no backend required)
- Uses PapaParse for CSV parsing and Fuse.js for fuzzy matching
- Comprehensive normalization datasets for teams and player names
- Responsive design with dark/light theme support