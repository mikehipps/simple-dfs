#!/usr/bin/env python3
"""
Rotowire NHL Lineup Scraper
===========================

Prototype scraper that pulls projected NHL lineups, power-play units, and injury
statuses from https://www.rotowire.com/hockey/nhl-lineups.php using the
``crawl4ai`` Playwright wrapper.

The script normalizes the lineup boxes into a tabular structure so the output
CSV can be merged into existing FanDuel / projection workflows.

Usage:
    python scrapers/rotowire_nhl_lineups.py --out data/nhl_lineups.csv

Notes:
- Requires ``crawl4ai``, ``beautifulsoup4``, and Playwright. Install via:
      pip install crawl4ai beautifulsoup4
      python -m playwright install chromium
- This is an initial pass; mapping to in-house IDs or slate filtering will be
  layered on once the desired schema is finalized.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

LOGGER = logging.getLogger(__name__)
ROTOWIRE_NHL_LINEUPS_URL = "https://www.rotowire.com/hockey/nhl-lineups.php"
SCRAPERS_DIR = Path(__file__).resolve().parent
os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(SCRAPERS_DIR))


@dataclass
class LineupRow:
    game_time: str
    home_team: str
    away_team: str
    team_role: str  # "home" or "away"
    team_abbr: str
    team_name: str
    record: Optional[str]
    section: str  # e.g., GOALIE, POWER PLAY #1, INJURIES
    position: Optional[str]
    player_name: str
    player_href: Optional[str]
    injury_status: Optional[str]
    lineup_status: Optional[str]  # e.g., Confirmed, Expected (goalies)
    line_info: Optional[str]
    ou_info: Optional[str]


async def fetch_page_html(url: str = ROTOWIRE_NHL_LINEUPS_URL) -> str:
    """Return rendered HTML for the Rotowire NHL lineup page."""
    browser_config = BrowserConfig(
        headless=True,
        extra_args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-crash-reporter",
        ],
    )
    run_config = CrawlerRunConfig(
        wait_for="css:div.lineup__box",
        wait_for_timeout=45000,
    )
    async with AsyncWebCrawler(config=browser_config) as crawler:
        LOGGER.info("Navigating to %s", url)
        result = await crawler.arun(url=url, crawler_config=run_config)
        html = getattr(result, "html", None) or getattr(result, "page_content", None)
        if not html:
            raise RuntimeError("Crawler returned empty HTML content")
        LOGGER.info("Page loaded; extracting HTML")
        return html


def extract_text(node: Optional[Tag], default: Optional[str] = None) -> Optional[str]:
    if node is None:
        return default
    return node.get_text(strip=True)


def extract_attr(node: Optional[Tag], attr: str, default: Optional[str] = None) -> Optional[str]:
    if not node:
        return default
    value = node.get(attr)
    return value if value is not None else default


def parse_lineup_boxes(html: str) -> List[LineupRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[LineupRow] = []
    lineup_nodes = soup.select("div.lineup.is-nhl")
    LOGGER.info("Found %d lineup boxes", len(lineup_nodes))
    for lineup in lineup_nodes:
        try:
            rows.extend(parse_single_lineup(lineup))
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.warning("Failed to parse lineup box: %s", exc, exc_info=True)
    return rows


def parse_single_lineup(lineup: Tag) -> List[LineupRow]:
    rows: List[LineupRow] = []
    game_time = extract_text(lineup.select_one(".lineup__time"), "")

    teams_container = lineup.select_one(".lineup__teams")
    away_team_abbr = extract_text(teams_container.select_one(".lineup__team.is-visit .lineup__abbr"), "")
    home_team_abbr = extract_text(teams_container.select_one(".lineup__team.is-home .lineup__abbr"), "")

    matchup = lineup.select_one(".lineup__matchup")
    away_team_name = extract_text(matchup.select_one(".lineup__mteam.is-visit"), away_team_abbr)
    home_team_name = extract_text(matchup.select_one(".lineup__mteam.is-home"), home_team_abbr)
    away_record = extract_text(matchup.select_one(".lineup__mteam.is-visit .lineup__wl"))
    home_record = extract_text(matchup.select_one(".lineup__mteam.is-home .lineup__wl"))

    odds = lineup.select("div.lineup__odds-item")
    line_info = extract_text(odds[0]) if len(odds) > 0 else None
    ou_info = extract_text(odds[1]) if len(odds) > 1 else None

    away_list = lineup.select_one("ul.lineup__list.is-visit")
    home_list = lineup.select_one("ul.lineup__list.is-home")

    rows.extend(
        parse_team_list(
            ul_node=away_list,
            team_role="away",
            team_abbr=away_team_abbr,
            team_name=away_team_name,
            record=away_record,
            game_time=game_time,
            opponent=home_team_abbr,
            home_team=home_team_abbr,
            line_info=line_info,
            ou_info=ou_info,
        )
    )
    rows.extend(
        parse_team_list(
            ul_node=home_list,
            team_role="home",
            team_abbr=home_team_abbr,
            team_name=home_team_name,
            record=home_record,
            game_time=game_time,
            opponent=away_team_abbr,
            home_team=home_team_abbr,
            line_info=line_info,
            ou_info=ou_info,
        )
    )
    return rows


def parse_team_list(
    ul_node: Optional[Tag],
    *,
    team_role: str,
    team_abbr: str,
    team_name: str,
    record: Optional[str],
    game_time: str,
    opponent: str,
    home_team: str,
    line_info: Optional[str],
    ou_info: Optional[str],
) -> List[LineupRow]:
    if ul_node is None:
        return []

    rows: List[LineupRow] = []
    current_section = "LINEUP"

    highlight = ul_node.select_one("li.lineup__player-highlight")
    if highlight:
        goalie_name = extract_text(highlight.select_one(".lineup__player-highlight-name a"), "")
        goalie_href = extract_attr(highlight.select_one(".lineup__player-highlight-name a"), "href")
        status = extract_text(highlight.select_one(".flex-row"))
        rows.append(
            LineupRow(
                game_time=game_time,
                home_team=home_team,
                away_team=opponent if team_role == "home" else team_abbr,
                team_role=team_role,
                team_abbr=team_abbr,
                team_name=team_name.strip(),
                record=record.strip() if record else None,
                section="GOALIE",
                position=None,
                player_name=goalie_name,
                player_href=normalize_link(goalie_href),
                injury_status=None,
                lineup_status=status,
                line_info=line_info,
                ou_info=ou_info,
            )
        )

    for item in ul_node.find_all("li", recursive=False):
        classes = item.get("class", [])
        if "lineup__player-highlight" in classes:
            continue
        if "lineup__title" in classes:
            title_text = extract_text(item, "").upper()
            current_section = title_text or current_section
            continue
        if "lineup__player" in classes:
            pos = extract_text(item.select_one(".lineup__pos"))
            link_node = item.select_one("a")
            name = extract_text(link_node, "")
            href = extract_attr(link_node, "href")
            injury = extract_text(item.select_one(".lineup__inj"))
            rows.append(
                LineupRow(
                    game_time=game_time,
                    home_team=home_team,
                    away_team=opponent if team_role == "home" else team_abbr,
                    team_role=team_role,
                    team_abbr=team_abbr,
                    team_name=team_name.strip(),
                    record=record.strip() if record else None,
                    section=current_section,
                    position=pos,
                    player_name=name,
                    player_href=normalize_link(href),
                    injury_status=injury,
                    lineup_status=None,
                    line_info=line_info,
                    ou_info=ou_info,
                )
            )
    return rows


def normalize_link(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    if href.startswith("http"):
        return href
    return f"https://www.rotowire.com{href}"


async def scrape_rotowire_lineups() -> List[LineupRow]:
    html = await fetch_page_html()
    rows = parse_lineup_boxes(html)
    LOGGER.info("Extracted %d lineup rows", len(rows))
    return rows


def export_to_csv(rows: Sequence[LineupRow], output_path: Path) -> None:
    df = pd.DataFrame([asdict(row) for row in rows])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    LOGGER.info("Saved %d rows to %s", len(df), output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Rotowire NHL lineups into a CSV file.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("scrapers/output/rotowire_nhl_lineups.csv"),
        help="Path to the CSV file to create (default: scrapers/output/rotowire_nhl_lineups.csv)",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="If set, prints a preview instead of writing to disk.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    rows = asyncio.run(scrape_rotowire_lineups())
    if args.no_export:
        preview = pd.DataFrame([asdict(row) for row in rows])
        print(preview.head(20))
    else:
        export_to_csv(rows, args.out)


if __name__ == "__main__":
    main()
