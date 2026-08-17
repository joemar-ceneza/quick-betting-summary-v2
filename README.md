# Quick Summary Scraper

## What This Does
Logs into the LEO website and scrapes a player's account details (status,
currency, table limit), their Live Casino Player Bet List, and their recent
statement history for the selected date range, then builds a one-row quick
summary per player:

Date, Username, Currency, Status, Table Limit, Products Played, Total Rounds
Played, Total Won, Total Lose, Total Draw, Total Member Win/Loss, Winning
Percentage, Max Stake per Round, Biggest Winning Amount, Biggest Losing Amount,
Betting Options Placed, Betting Pattern.

In the browser app you scrape one player at a time (username typed in the
sidebar); the command-line entry point scrapes every username in
`usernames.txt`.

Each summary card also has a collapsible **Day-by-Day Comparison** table:
rounds, won/lose/draw, member win/loss, win %, and max stake for each day in
the 8 days ending on *Date to* (independent of the selected range), with ▲/▼
deltas vs the previous day. Days with no bets are hidden.

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
4. Copy `.env.example` to `.env` and fill in your LEO credentials — required
   for the browser app (or set them in Streamlit secrets); the CLI prompts if
   not set
5. (CLI / Task Scheduler runs only) Create `usernames.txt` in the project root
   with one player username per line

## How to Run

### Browser report (recommended)
```
streamlit run app.py
```
Opens the report in your browser. Enter a username and the date range in the
sidebar (**Date from** defaults to yesterday, **Date to** to today), then click
**Scrape & Summarize**. The player is shown as a summary card with all fields
plus the day-by-day comparison. The main summary reflects the selected range,
and the pull is automatically extended back to the 8 days ending on *Date to*
so the comparison always has a complete window. The report follows
Streamlit's light/dark theme.

### Command line (for Task Scheduler / unattended runs)
```
python main.py               # report date = yesterday
python main.py 06/30/2026    # report date = specific day (MM/DD/YYYY)
```

Scrapes every username in `usernames.txt`. The bet list is pulled from the
report date 12:00 AM to the following day 12:00 AM, matching the LEO date
filter used by scorecard-script. The CLI writes the summaries and conclusions
to the console and `logs/automation.log`.

`main.py` also runs as a standalone PyInstaller exe for unattended runs —
place `.env` and `usernames.txt` next to the exe.

## Project Structure
```
quick-betting-summary/
├── app.py               # Browser report entry point (Streamlit orchestrator)
├── ui.py                # Browser presentation layer — theme, summary cards, day-by-day comparison
├── main.py              # CLI entry point — same workflow, results in the log
├── config.py            # All settings, constants, and configurations
├── scraper.py           # LEO login, account details, bet list, and statement history
├── parser.py            # Bet-list rows → flat round records + round accessors
├── summary.py           # Computes the summary fields + day-by-day breakdown (Betting Pattern is user-entered)
├── conclusion.py        # Builds the conclusion (always "Normal", shown in green)
├── utils.py             # Generic helpers (retry, frames, click retry)
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Tooling config (black line-length)
├── .env.example         # Template for LEO credentials
├── .env                 # LEO credentials — never committed
├── usernames.txt        # One player username per line (CLI only) — never committed
└── logs/                # automation.log + error screenshots
```

## Logs
Logs are saved to `logs/automation.log`.
Screenshots on errors are saved to `logs/screenshots/`.
