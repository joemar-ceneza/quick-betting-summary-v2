# Quick Summary Scraper

## What This Does
Logs into the LEO website, and for each username in `usernames.txt` scrapes the
player's account details (status, currency, table limit) and their Live Casino
Player Bet List for the report date, then builds a one-row quick summary per
player:

Date, Username, Currency, Status, Table Limit, Products Played, Total Rounds
Played, Total Won, Total Lose, Total Draw, Total Member Win/Loss, Winning
Percentage, Max Stake per Round, Biggest Winning Amount, Biggest Losing Amount,
Betting Options Placed, Betting Pattern.

Each summary card lets you type or edit the **Betting Pattern** and
**Conclusion** directly in the browser — there is no automatic detection. Any
field that cannot be read is returned as `-` / empty instead of failing the
run. Baccarat tables named A–Z (e.g. H22) or 1–9 (e.g. 5 30) are reported as a
single **SBO Baccarat** product. Results are shown in the browser only —
nothing is written to disk apart from logs.

## Requirements
- Python 3.10+
- Windows OS
- Access to the LEO website (internal host — run where LEO is reachable, e.g. over the company VPN)

## Setup
1. Clone or download this project
2. Create virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   playwright install
   ```
4. Copy `.env.example` to `.env` and fill in your LEO credentials
   (optional — the script prompts if not set)
5. Create `usernames.txt` in the project root with one player username per line

## How to Run

### Browser report (recommended)
```
streamlit run app.py
```
Opens the report in your browser. Enter a username and the date range in the
sidebar (**Date from** defaults to yesterday, **Date to** to today), then click
**Scrape & Summarize**. The player is shown as a summary card with all fields.

### Command line (for Task Scheduler / unattended runs)
```
python main.py               # report date = yesterday
python main.py 06/30/2026    # report date = specific day (MM/DD/YYYY)
```

Either way the bet list is pulled from the report date 12:00 AM to the
following day 12:00 AM, matching the LEO date filter used by scorecard-script.
The CLI writes the summaries and conclusions to the console and
`logs/automation.log`.

## Project Structure
```
quick-summary/
├── app.py               # Browser report entry point (Streamlit orchestrator)
├── ui.py                # Browser report presentation layer
├── main.py              # CLI entry point — same workflow, results in the log
├── config.py            # All settings, constants, and configurations
├── scraper.py           # LEO login, account details, and bet-list scraping
├── parser.py            # Bet-list rows → flat round records + round accessors
├── summary.py           # Computes the summary fields (Betting Pattern is user-entered)
├── conclusion.py        # Builds the conclusion (always "Normal", shown in green)
├── utils.py             # Generic helpers (retry, frames, click retry)
├── .env                 # LEO credentials — never committed
├── usernames.txt        # One player username per line
└── logs/                # automation.log + error screenshots
```

## Logs
Logs are saved to `logs/automation.log`.
Screenshots on errors are saved to `logs/screenshots/`.
