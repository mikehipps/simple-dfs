#!/usr/bin/env python3
"""
Backward-compatible wrapper for the unified FanDuel MME picker.

Running this script behaves the same as:
    python fd_mme_picker.py --sport nhl
"""

from mme_picker.core import main


if __name__ == "__main__":
    main(default_sport="nhl")
