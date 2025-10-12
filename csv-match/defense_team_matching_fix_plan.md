# Defense Team Matching Fix Plan

## Problem Analysis

### Current Issue
Three defense teams are failing to match between CSV files due to naming variations:

**Primary File (Projections):**
- Name: `Colts` | Team: `IND`
- Name: `49ers` | Team: `SF` 
- Name: `Jaguars` | Team: `JAX`

**Secondary File:**
- Name: `Indianapolis Colts` | Team: `IND`
- Name: `San Francisco 49ers` | Team: `SF`
- Name: `Jacksonville Jaguars` | Team: `JAC`

### Root Cause
The current system handles D/ST normalization well when names contain D/ST patterns, but doesn't handle the conversion from short team names to full team names for defense teams.

## Required Changes

### 1. Update Team Mappings in `nfl_teams.json`

Add the following mappings to the `map` section:

```json
"indianapolis colts": "IND",
"san francisco 49ers": "SF", 
"jacksonville jaguars": "JAX"
```

### 2. Enhanced D/ST Name Normalization

The current D/ST normalization in [`index.html`](index.html:395-398) only handles D/ST pattern detection. We need to enhance it to also handle short team name → full team name conversion for defense teams.

Current code:
```javascript
function dstNormalizedName(name, teamCode) {
  if (!teamCode) return normName(name);
  return normText(teamFullNameFromCode(teamCode)).split(" ").join(" ");
}
```

Proposed enhancement: Add logic to detect when a defense team name is just the short team name and convert it to the full team name.

### 3. Consider Additional Team Mappings

To prevent similar issues with other teams, consider adding mappings for:
- All team short names to full names
- Common variations that might appear in defense team naming

## Implementation Strategy

### Phase 1: Immediate Fix
1. Add the 3 specific team mappings to `nfl_teams.json`
2. Test with the provided examples

### Phase 2: Comprehensive Prevention  
1. Add mappings for all NFL teams from short names to full names
2. Enhance D/ST detection to handle more naming patterns

### Phase 3: Manual Review Enhancement (Future)
Implement a manual lookup feature in the review process for "No match" cases to allow users to manually select matches from the secondary file.

## Technical Details

### Current Team Code Resolution
The system already handles team code variations correctly:
- `JAX` and `JAC` both map to canonical `JAX`
- Team codes are normalized via `canonTeam()` function

### Name Normalization Flow
1. Raw name → `normText()` → text normalization
2. Normalized text → `normName()` → nickname/suffix processing  
3. If D/ST detected → `dstNormalizedName()` → team-based normalization
4. **MISSING**: Short team name → full team name conversion

## Testing Plan

Test cases to verify the fix:
1. `Colts` + `IND` → matches `Indianapolis Colts` + `IND`
2. `49ers` + `SF` → matches `San Francisco 49ers` + `SF`  
3. `Jaguars` + `JAX` → matches `Jacksonville Jaguars` + `JAC`

## Next Steps

1. Switch to Code mode to implement the JSON file changes
2. Test the specific team mappings
3. Consider implementing the enhanced D/ST normalization if needed
4. Add comprehensive team mappings for future prevention