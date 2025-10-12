# CSV Match - Technical Documentation

## Technologies Used

### Core Technologies
- **HTML5/CSS3/JavaScript**: Pure client-side implementation
- **PapaParse**: CSV parsing library (CDN)
- **Fuse.js**: Fuzzy string matching library (CDN)
- **Browser localStorage**: Persistent alias storage

### Development Tools
- **Python 3+**: Dataset building and normalization
- **JSON**: Data serialization format for team mappings and name data

### External Dependencies
```javascript
// CDN dependencies in index.html
<script src="https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
```

## Development Setup

### Project Structure
```
dfs_sbs/
├── index.html                 # Main application
├── README.md                  # Project documentation
├── scripts/
│   └── build_name_datasets.py # Dataset generation script
├── data/                      # Generated and static data files
│   ├── nfl_teams.json         # NFL team mappings
│   ├── nba_teams.json         # NBA team mappings  
│   ├── mlb_teams.json         # MLB team mappings
│   ├── nhl_teams.json         # NHL team mappings
│   ├── nicknames_common.json  # Generated nickname mappings
│   ├── suffixes.json          # Generated suffix list
│   ├── dst_patterns.json      # D/ST detection patterns
│   └── *overrides.json        # Manual data overrides
├── docs/
│   └── name_normalization_resources.md
└── third_party/
    └── name_data/             # Vendored datasets
        ├── joshfraser_nicknames.json
        ├── nameparser_suffixes.json
        └── README.md
```

### Data Generation Process
```bash
# Regenerate nickname and suffix datasets
python scripts/build_name_datasets.py
```

### Build Script ([`scripts/build_name_datasets.py`](../scripts/build_name_datasets.py))
- Merges vendored datasets with local overrides
- Normalizes all tokens to lowercase, trimmed format
- Generates optimized JSON files for runtime use

## Technical Constraints

### Browser Compatibility
- **Modern Browsers**: Chrome, Firefox, Safari, Edge
- **Required Features**: File API, localStorage, ES6+
- **No Support**: Internet Explorer

### Performance Considerations
- **Memory**: All processing in browser memory, limited by available RAM
- **File Size**: CSV files should be reasonable for browser processing
- **Search**: Fuse.js configured with 0.12 threshold for fuzzy matching

### Data Constraints
- **CSV Format**: Must be valid CSV with headers
- **Encoding**: UTF-8 recommended
- **Size**: Practical limits for browser processing (~10MB per file)

## Key Implementation Details

### Name Normalization Pipeline
```javascript
function normName(name) {
  const t = normText(name);  // Text normalization
  const parts = t.split(" ").filter(Boolean).map(w => NICK[w] || w).join(" ").split(" ");
  const cleaned = parts.filter(w => !SUFFIXES.has(w));  // Suffix removal
  return cleaned.join(" ");
}
```

### Team Canonicalization
- All teams mapped to 3-letter codes (NFL: "ARI", NBA: "PHX", etc.)
- Comprehensive alias mappings handle variations
- Team isolation prevents cross-sport matching

### D/ST Detection and Normalization
```javascript
function isDSTName(n) { return DST_REGEX.test(n || ""); }
function dstNormalizedName(name, teamCode) {
  if (!teamCode) return normName(name);
  return normText(teamFullNameFromCode(teamCode)).split(" ").join(" ");
}
```

## Tool Usage Patterns

### Data Updates
1. Update vendored datasets in `third_party/name_data/`
2. Run build script: `python scripts/build_name_datasets.py`
3. Test with sample data
4. Deploy updated data files

### Team Mapping Updates
1. Edit sport-specific team JSON files
2. Update alias mappings and full name mappings
3. Test with affected sports data

### Development Workflow
1. Modify [`index.html`](../index.html) for feature changes
2. Test with sample CSV files
3. Update documentation as needed
4. Deploy single HTML file

## Testing Strategy
- Manual testing with sample sports data
- Cross-browser compatibility testing
- Performance testing with large datasets
- Edge case testing (special characters, missing data)

## Deployment
- Single HTML file deployment
- No build process required
- Static hosting (GitHub Pages, S3, etc.)
- Data files hosted alongside application