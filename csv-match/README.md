# CSV Match

Utility data files for normalizing sports team names and player aliases.

## Reference data

- `data/nfl_teams.json`: canonical NFL team names with alias mapping.
- `data/nba_teams.json`: canonical NBA team names with alias mapping.
- `data/mlb_teams.json`: canonical MLB team names with alias mapping.
- `data/nhl_teams.json`: canonical NHL team names with alias mapping.
- `data/nicknames_common.json`: alias-to-canonical first-name mappings generated from the vendored [`joshfraser/nicknames`](third_party/name_data/README.md) dataset plus local overrides.
- `data/suffixes.json`: normalized suffix list generated from the vendored [`nameparser` configuration](third_party/name_data/README.md) with local overrides.

See [docs/name_normalization_resources.md](docs/name_normalization_resources.md) for open datasets that could expand the nickname and suffix coverage.

Regenerate the nickname and suffix artifacts with:

```
python scripts/build_name_datasets.py
```
