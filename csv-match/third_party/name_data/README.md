# Vendored name datasets

This directory vendors upstream resources so we can build normalization tables without requiring network access.

- `joshfraser_nicknames.json` is adapted from the [MIT-licensed `joshfraser/nicknames`](https://github.com/joshfraser/nicknames) project. The data was transcribed for offline use and retains the original mapping of canonical first names to their common diminutives.
- `nameparser_suffixes.json` is adapted from the [BSD-licensed `python-nameparser`](https://github.com/derek73/python-nameparser) suffix configuration.

Run `scripts/build_name_datasets.py` after updating either file to regenerate the normalized artifacts in `data/`.
