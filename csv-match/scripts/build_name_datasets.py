#!/usr/bin/env python3
"""Generate normalized nickname and suffix datasets from vendored resources."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Set

ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "third_party" / "name_data"
DATA_DIR = ROOT / "data"

NICKNAME_VENDOR_PATH = VENDOR_DIR / "joshfraser_nicknames.json"
SUFFIX_VENDOR_PATH = VENDOR_DIR / "nameparser_suffixes.json"
NICKNAME_OVERRIDES_PATH = DATA_DIR / "nickname_overrides.json"
SUFFIX_OVERRIDES_PATH = DATA_DIR / "suffix_overrides.json"
NICKNAME_OUTPUT_PATH = DATA_DIR / "nicknames_common.json"
SUFFIX_OUTPUT_PATH = DATA_DIR / "suffixes.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def normalize_token(token: str) -> str:
    return " ".join(token.split()).strip().lower()


def build_nickname_map(vendor: Dict[str, Iterable[str]], overrides: Dict[str, str]) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for canonical, aliases in vendor.items():
        canonical_norm = normalize_token(canonical)
        if not canonical_norm:
            continue
        alias_map.setdefault(canonical_norm, canonical_norm)
        for alias in aliases:
            alias_norm = normalize_token(str(alias))
            if not alias_norm:
                continue
            alias_map.setdefault(alias_norm, canonical_norm)
    for alias, canonical in overrides.items():
        alias_norm = normalize_token(str(alias))
        canonical_norm = normalize_token(str(canonical))
        if not alias_norm or not canonical_norm:
            continue
        alias_map[alias_norm] = canonical_norm
    return dict(sorted(alias_map.items()))


def build_suffixes(vendor_suffixes: Iterable[str], overrides: Iterable[str]) -> List[str]:
    suffix_set: Set[str] = set()
    for token in vendor_suffixes:
        token_norm = normalize_token(str(token).replace(".", "").replace(",", ""))
        if token_norm:
            suffix_set.add(token_norm)
    for token in overrides:
        token_norm = normalize_token(str(token).replace(".", "").replace(",", ""))
        if token_norm:
            suffix_set.add(token_norm)
    return sorted(suffix_set)


def main() -> None:
    vendor_nicknames = load_json(NICKNAME_VENDOR_PATH, {})
    nickname_overrides = load_json(NICKNAME_OVERRIDES_PATH, {})
    nickname_map = build_nickname_map(vendor_nicknames, nickname_overrides)
    with NICKNAME_OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(nickname_map, fh, indent=2, ensure_ascii=False, sort_keys=True)

    vendor_suffixes = load_json(SUFFIX_VENDOR_PATH, [])
    suffix_overrides = load_json(SUFFIX_OVERRIDES_PATH, [])
    suffix_list = build_suffixes(vendor_suffixes, suffix_overrides)
    with SUFFIX_OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(suffix_list, fh, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
