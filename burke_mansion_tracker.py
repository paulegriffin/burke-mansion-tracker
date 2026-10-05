#!/usr/bin/env python3
"""
Burke Mansion Macon — Room Occupancy Tracker
Runs daily via GitHub Actions. Saves to burke_mansion_occupancy_log.csv
in the repo root, which is then committed and served to the dashboard.
"""

from __future__ import annotations

import asyncio
import csv
import html as htmllib
import os
import random
import re
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Room definitions
# ---------------------------------------------------------------------------
ROOMS = [
    {"name": "The Heirloom Suite",           "url": "https://www.burkemansionmacon.com/rooms/room-1"},
    {"name": "The Veranda Suite",             "url": "https://www.burkemansionmacon.com/rooms/room-2"},
    {"name": "Sweet Georgia Suite",           "url": "https://www.burkemansionmacon.com/rooms/room-3"},
    {"name": "The Front Porch Room",          "url": "https://www.burkemansionmacon.com/rooms/room-4"},
    {"name": "Cherry Blossom Carriage House", "url": "https://www.burkemansionmacon.com/rooms/room-5"},
    {"name": "Capricorn Suite",               "url": "https://www.burkemansionmacon.com/rooms/room-6"},
    {"name": "The Camellia Room",             "url": "https://www.burkemansionmacon.com/rooms/the-camellia-room"},
    {"name": "The Magnolia Manor Suite",      "url": "https://www.burkemansionmacon.com/rooms/the-magnolia-manor-suite"},
]

ROOM_RATES = {
    "The Heirloom Suite": 215,
    "The Veranda Suite": 250,
    "Sweet Georgia Suite": 275,
    "The Front Porch Room": 250,
    "Cherry Blossom Carriage House": 450,
    "Capricorn Suite": 250,
    "The Camellia Room": 275,
    "The Magnolia Manor Suite": 250,
}

TAX_RATE    = 0.16
NIGHTLY_FEE = 8.00

SCRIPT_DIR  = Path(__file__).parent.resolve()
CSV_LOG     = SCRIPT_DIR / "burke_mansion_occupancy_log.csv"
TODAY_STR   = date.today().isoformat()
CSV_HEADERS = ["snapshot_date", "room", "date", "status"]

DELAY_MIN = 2
DELAY_MAX = 4


def parse_calendar_html(raw_html: str) -> dict[str, str]:
    content = htmllib.unescape(raw_html)
    td_re = re.compile(r'<td\b([^>]*\bdata-day="([^"]+)"[^>]*)>', re.DOTALL)
    seen: dict[str, str] = {}
    for m in td_re.finditer(content):
        attrs_block = m.group(1)
        day_str     = m.group(2)
        if 'data-outside="true"' in attrs_block: continue
        if 'data-hidden="true"'  in attrs_block: continue
        if day_str in seen: continue
        seen[day_str] = "Booked" if 'data-disabled="true"' in attrs_block else "Available"
    return seen


async def fetch_page_html(page, url: str) -> str:
    await page.goto(url, wait_until="networkidle", timeout=60_000)
    try:
        await page.wait_for_selector('[data-day]', timeout=10_000)
    except Exception:
        await page.wait_for_load_state("domcontentloaded")
    return await page.content()


def ensure_csv_header():
    if not CSV_LOG.exists():
        with open(CSV_LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADERS)


def append_rows(rows: list[list]):
    with open(CSV_LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def load_prior_statuses(snapshot_date: str) -> dict[tuple[str, str], str]:
    if not CSV_LOG.exists():
        return {}
    rows = []
    with open(CSV_LOG, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("snapshot_date", "") < snapshot_date:
                rows.append(row)
    corrected: dict[tuple[str, str], str] = {}
    for row in sorted(rows, key=lambda r: (r["snapshot_date"], r["room"], r["date"])):
        key = (row["room"], row["date"])
        if row["date"] < row["snapshot_date"]:
            corrected[key] = corrected.get(key, "Available")
        else:
            corrected[key] = row["status"]
    return corrected


def correct_past_dates(room_name, date_map, prior_statuses, snapshot_date):
    corrected = {}
    for stay_date, status in date_map.items():
        if stay_date < snapshot_date:
            corrected[stay_date] = prior_statuses.get((room_name, stay_date), "Available")
        else:
            corrected[stay_date] = status
    return corrected


async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    print(f"Burke Mansion Tracker — {TODAY_STR}")
    ensure_csv_header()
    prior_statuses = load_prior_statuses(TODAY_STR)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        for i, room in enumerate(ROOMS):
            room_name = room["name"]
            room_url  = room["url"]
            print(f"[{i+1}/{len(ROOMS)}] {room_name}")
            try:
                html_content = await fetch_page_html(page, room_url)
                date_map = parse_calendar_html(html_content)
                date_map = correct_past_dates(room_name, date_map, prior_statuses, TODAY_STR)
                if not date_map:
                    print(f"  WARNING: No dates found.")
                else:
                    rows = [[TODAY_STR, room_name, d, s] for d, s in sorted(date_map.items())]
                    append_rows(rows)
                    booked = sum(1 for s in date_map.values() if s == "Booked")
                    print(f"  {len(date_map)} dates — {booked} booked")
            except Exception as exc:
                print(f"  ERROR: {exc}")
                traceback.print_exc()

            if i < len(ROOMS) - 1:
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        await browser.close()

    print(f"\nDone. CSV saved to {CSV_LOG}")


if __name__ == "__main__":
    asyncio.run(main())
