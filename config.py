import os
import sys

# When running as a PyInstaller exe, resolve paths relative to the exe.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Browser
HEADLESS = True

# Paths (absolute so Task Scheduler works correctly)
USERNAME_FILE = os.path.join(BASE_DIR, "usernames.txt")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "automation.log")
SCREENSHOT_DIR = os.path.join(LOG_DIR, "screenshots")

# LEO scraper
LEO_LOGIN_URL = "http://leo-a01.sbobet.com.tw:8088/Default.aspx"
LEO_MAX_RETRIES = 3
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2
CURRENCY_MAP = {"Pp": "IDR", "TB": "THB"}
SBO_BACCARAT_LABEL = "SBO Baccarat"  # reporting label for Baccarat tables A-Z / 1-9

# Timeouts (milliseconds)
ELEMENT_TIMEOUT = 300000
TABLE_TIMEOUT = 15000

# Betting-pattern tuning (same 9 tag definitions as betting-behavior)
MAIN_SIDES = ("Banker", "Player")
LONG_HISTORY_MIN_STREAK = 6  # consecutive bets on same table to count as "long stay"
DRAGON_MIN_STREAK = 6  # straight Banker-only or Player-only bets to count as a dragon
PINGPONG_MIN_BETS = 4  # consecutive alternating B/P bets (B,P,B,P)
# Selections that can combine into a Mix Bet (no minimum number of rounds)
MIX_SELECTIONS = ("Banker", "Player", "Tie", "Banker Pair", "Player Pair")
DOUBLE_UP_FACTOR = 2.0  # stake must be >= this x previous stake after a loss
OCCASIONAL_GAP_MINUTES = 15  # minutes of inactivity before a bet counts as occasional
PATTERN_THRESHOLD = 0.15  # share of rounds a flag needs to appear in the Betting Pattern field

# Design tokens (web report — theme-neutral so the page follows Streamlit's
# light/dark toggle; accents chosen to stay readable on both backgrounds)
T_SUCCESS = "37B24D"
T_WARNING = "F59F00"
T_DANGER = "F03E3E"
T_NEUTRAL = "808693"  # mid gray used at low opacity for panels/borders
