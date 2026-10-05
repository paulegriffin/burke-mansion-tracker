# Burke Mansion Macon — Availability Tracker

Auto-scrapes room availability daily and publishes a live dashboard.

**Live Dashboard:** https://paulegriffin.github.io/burke-mansion-tracker

## How it works
- GitHub Actions runs the scraper every day at 9 AM Eastern
- Results are saved to `burke_mansion_occupancy_log.csv` in this repo
- The dashboard at the link above reads the CSV and displays current availability, MTD stats, and full history
- No local computer required

## Manual trigger
Go to the **Actions** tab on GitHub and click **Run workflow** to trigger a scrape immediately.
