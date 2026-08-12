"""Scrapes each player's account details and bet list from the Leo website.

The public entry point owns the browser lifecycle (open -> login -> per-player
scrape -> close) and returns one raw dict per player. summary.build_summaries()
turns those raw dicts into the final quick-summary records.

Note: Leo is an internal host (usually reached over the company VPN). VPN setup
is intentionally out of scope here — run this where Leo is already reachable.
"""

import logging
import os
from datetime import datetime
from typing import Any

from playwright.sync_api import sync_playwright, Playwright, TimeoutError as PlaywrightTimeoutError

import config
import utils


# ======================================================
# BROWSER CONTEXT / ERROR CAPTURE
# ======================================================
def _build_context(p: Playwright) -> tuple:
    """Launch browser with a fresh context each run."""
    browser = p.chromium.launch(headless=config.HEADLESS)
    context = browser.new_context()
    return browser, context


def _save_error_screenshot(page: Any, label: str) -> None:
    """Save a screenshot of the current page to logs/screenshots/ for debugging."""
    if page is None:
        return
    try:
        os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
        safe_label = "".join(c for c in label if c.isalnum() or c in ("_", "-"))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(config.SCREENSHOT_DIR, f"error_{safe_label}_{stamp}.png")
        page.screenshot(path=path, full_page=True)
        logging.error("Screenshot saved: %s", path)
    except Exception as exc:  # noqa: BLE001 - never mask the original error
        logging.warning("Could not save error screenshot: %s", exc)


# ======================================================
# LOGIN
# ======================================================
def _login_leo(context: Any, username: str, password: str) -> Any:
    """Open a new Leo page, log in, dismiss the warning popup, return the page."""
    page = context.new_page()
    page.on("dialog", utils.handle_dialog)
    page.goto(config.LEO_LOGIN_URL)
    page.locator("#txtUsername").fill(username)
    page.locator("#txtPassword").fill(password)
    utils.click_with_retry(page.locator("#btnLogin"))
    page.wait_for_load_state("load", timeout=config.ELEMENT_TIMEOUT)

    try:
        if page.locator("#tblExchange").is_visible(timeout=config.ELEMENT_TIMEOUT):
            logging.info("Login warning popup detected — clicking continue...")
            page.locator("#continue").click()
    except Exception:  # noqa: BLE001 - popup is optional
        pass

    utils.get_frame(page, "menu")
    logging.info("Successfully logged into the LEO website.")
    return page


# ======================================================
# ACCOUNT DETAILS (status + currency + table limit)
# ======================================================
def _get_account_status(contents_frame: Any) -> str:
    """Read the Closed/Suspend buttons on the customer page. Returns Active/Suspended/Closed."""
    closed_value = contents_frame.locator("#btnClosed").get_attribute("value")
    suspended_value = contents_frame.locator("#btnSuspend").get_attribute("value")
    if closed_value == "YES":
        return "Closed"
    if suspended_value == "YES":
        return "Suspended"
    return "Active"


def _get_account_details(leo_page: Any, username: str) -> dict:
    """Look up the player's status, currency and VIP table limit from Leo.

    Returns "-" for any field that cannot be read so the summary can still be
    built for the remaining fields.
    """
    details = {"status": "-", "currency": "-", "table_limit": "-"}
    try:
        menu_frame = utils.get_frame(leo_page, "menu")
        menu_frame.fill("#T1", username)
        utils.click_with_retry(menu_frame.locator(".Button"))

        contents_frame = utils.get_frame(leo_page, "contents")
        contents_frame.wait_for_selector("#formShow", timeout=config.ELEMENT_TIMEOUT)

        details["status"] = _get_account_status(contents_frame)
        raw_text = contents_frame.locator("//tr[th[contains(text(),'Outstanding Txn')]]/td/span").inner_text()
        code = raw_text.split()[0]
        details["currency"] = config.CURRENCY_MAP.get(code, code)

        menu_frame.click("#detail")
        itop_frame = utils.get_frame(leo_page, "itop")
        itop_frame.wait_for_selector("#Setting", timeout=config.ELEMENT_TIMEOUT)
        itop_frame.click("#Setting")

        icontents_frame = utils.get_frame(leo_page, "icontents")
        icontents_frame.wait_for_selector("td:has-text('Live Casino & Casino Games')", timeout=config.ELEMENT_TIMEOUT)
        icontents_frame.click("td:has-text('Live Casino & Casino Games')")
        icontents_frame.wait_for_selector(".SectionHead", timeout=config.ELEMENT_TIMEOUT)
        details["table_limit"] = (icontents_frame.locator("#LcTableLimit option:checked").text_content() or "-").strip()

        logging.info(
            "Account details — status: %s | currency: %s | table limit: %s",
            details["status"], details["currency"], details["table_limit"],
        )
    except Exception as exc:  # noqa: BLE001 - details are optional, don't block the scrape
        logging.warning("Could not read full account details for %s: %s", username, exc)
    return details


# ======================================================
# STATEMENT HISTORY (recent per-day win/lose)
# ======================================================
def _get_recent_statement(leo_page: Any) -> list[dict]:
    """Read the player's recent statement rows for Live Casino & Casino Games.

    Mirrors scorecard-script/watchlist-script: menu #stmt -> #tblExchange with
    #showCols checked; date is td[1], product td[3], win/lose td[4]. Returns
    [{"date": "MM/DD/YYYY", "win_lose": float}] — [] when it can't be read so
    the conclusion simply skips the history sentences.
    """
    try:
        menu_frame = utils.get_frame(leo_page, "menu")
        menu_frame.click("#stmt")

        contents_frame = utils.get_frame(leo_page, "contents")
        contents_frame.wait_for_load_state("networkidle", timeout=config.ELEMENT_TIMEOUT)
        contents_frame.locator("#showCols").wait_for(state="visible", timeout=config.ELEMENT_TIMEOUT)
        contents_frame.check("#showCols")
        contents_frame.wait_for_load_state("load", timeout=config.ELEMENT_TIMEOUT)

        days: list[dict] = []
        table_rows = contents_frame.locator("#tblExchange tbody tr:not(#totalRow)")
        for row_idx in range(table_rows.count()):
            cells = table_rows.nth(row_idx).locator("td")
            if cells.count() < 5:
                continue
            if "Live Casino & Casino Games" not in cells.nth(3).inner_text().strip():
                continue
            days.append({
                "date": cells.nth(1).inner_text().strip(),
                "win_lose": utils.clean_number(cells.nth(4).inner_text().strip()),
            })
        logging.info("Statement history: %d Live Casino day(s) found", len(days))
        return days
    except Exception as exc:  # noqa: BLE001 - history is optional, don't block the scrape
        logging.warning("Could not read statement history: %s", exc)
        return []


# ======================================================
# PLAYER BET LIST
# ======================================================
def _navigate_to_player_bet_list(leo_page: Any, from_date: str, to_date: str, username: str) -> Any:
    """Open the Live Casino -> Player Bet List report for username/date range.

    Returns the icontents frame with results, or None when the player has no
    bets in the range (empty report).
    """
    top_frame = utils.get_frame(leo_page, "banner")
    top_frame.click("a:has-text('Live Casino')")

    itop_frame = utils.get_frame(leo_page, "itop")
    itop_frame.wait_for_selector("a:has-text('Player Bet List')", timeout=config.ELEMENT_TIMEOUT)
    itop_frame.click("a:has-text('Player Bet List')")

    icontents_frame = utils.get_frame(leo_page, "icontents")
    icontents_frame.wait_for_selector("#form1", timeout=config.ELEMENT_TIMEOUT)

    icontents_frame.evaluate(f"""
        const from = document.querySelector("#txtFromDate");
        const to = document.querySelector("#txtToDate");
        if (from && to) {{
            from.value = "{from_date} 12:00:00 AM";
            to.value = "{to_date} 12:00:00 AM";
            from.dispatchEvent(new Event('input', {{ bubbles: true }}));
            from.dispatchEvent(new Event('change', {{ bubbles: true }}));
            to.dispatchEvent(new Event('input', {{ bubbles: true }}));
            to.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    """)

    icontents_frame.fill("#txtAccount", username)
    utils.click_with_retry(icontents_frame.locator("input.Button[value='Submit']"))
    icontents_frame.wait_for_load_state("networkidle", timeout=config.ELEMENT_TIMEOUT)

    try:
        icontents_frame.wait_for_selector("table.DT tbody tr td:not(#emptyCol)", timeout=config.TABLE_TIMEOUT)
    except PlaywrightTimeoutError:
        logging.info("No bet-list rows found for %s in %s to %s.", username, from_date, to_date)
        return None
    return icontents_frame


def _parse_bet_list_rows(icontents_frame: Any) -> list[list[str]]:
    """Flatten the bet-list table, expanding multi-line cells into round rows.

    Each visible row holds several lines per cell; this expands them so the game
    number lands only on the first line — the layout parser.parse_rows() expects.
    """
    bet_list_rows = icontents_frame.locator("table").nth(1).locator("tbody tr")
    bet_list_rows.first.wait_for(state="visible", timeout=config.ELEMENT_TIMEOUT)
    row_count = bet_list_rows.count()
    logging.info("Player Bet List visible rows: %d", row_count)

    final_data: list[list[str]] = []
    for row_idx in range(row_count):
        cells = bet_list_rows.nth(row_idx).locator("td")
        split_cells: list[list[str]] = []
        max_lines = 0
        for j in range(cells.count()):
            lines = [line.strip() for line in cells.nth(j).inner_text().strip().split("\n") if line.strip()]
            split_cells.append(lines)
            max_lines = max(max_lines, len(lines))

        for line_idx in range(max_lines):
            row: list[str] = []
            for col_idx, cell_lines in enumerate(split_cells):
                value = cell_lines[line_idx] if line_idx < len(cell_lines) else ""
                if col_idx == 0 and line_idx > 0:
                    value = ""
                row.append(value)
            final_data.append(row)

    return final_data


# ======================================================
# PER-PLAYER WORKFLOW
# ======================================================
def _scrape_player(leo_page: Any, username: str, from_date: str, to_date: str) -> dict:
    """Scrape one player's bet list and account details.

    The bet list is scraped first (known-good frame path); the account-details
    lookup navigates deep into the settings frames afterwards.
    """
    frame = _navigate_to_player_bet_list(leo_page, from_date, to_date, username)
    rows = _parse_bet_list_rows(frame) if frame is not None else []
    logging.info("Scraped %d source rows for %s (%s to %s)", len(rows), username, from_date, to_date)

    details = _get_account_details(leo_page, username)
    statement = _get_recent_statement(leo_page)
    return {
        "username": username,
        "status": details["status"],
        "currency": details["currency"],
        "table_limit": details["table_limit"],
        "rows": rows,
        "statement": statement,
    }


# ======================================================
# PUBLIC ENTRY POINT
# ======================================================
def run_scraper(usernames: list[str], from_date: str, to_date: str, leo_username: str, leo_password: str) -> list[dict]:
    """
    Log into Leo and scrape every player's bet list + account details.

    Dates are MM/DD/YYYY strings. Returns one dict per player:
    {"username", "status", "currency", "table_limit", "rows"} — a player that
    fails all retries is still returned with "-" details and empty rows so the
    run never dies on a single account.
    """
    players: list[dict] = []

    with sync_playwright() as p:
        browser, context = _build_context(p)
        leo_page = None
        try:
            leo_page = _login_leo(context, leo_username, leo_password)

            for i, username in enumerate(usernames, start=1):
                logging.info("=" * 70)
                logging.info("[%d/%d] Processing: %s", i, len(usernames), username)
                logging.info("=" * 70)

                for attempt in range(1, config.LEO_MAX_RETRIES + 1):
                    try:
                        players.append(_scrape_player(leo_page, username, from_date, to_date))
                        break
                    except Exception as e:  # noqa: BLE001 - keep processing remaining players
                        logging.warning("Attempt %d/%d failed for %s: %s", attempt, config.LEO_MAX_RETRIES, username, e)
                        if attempt == config.LEO_MAX_RETRIES:
                            logging.error("Skipping %s after %d failed attempts.", username, config.LEO_MAX_RETRIES)
                            _save_error_screenshot(leo_page, username)
                            players.append({
                                "username": username,
                                "status": "-",
                                "currency": "-",
                                "table_limit": "-",
                                "rows": [],
                                "statement": [],
                            })
        except Exception:
            _save_error_screenshot(leo_page, "fatal")
            raise
        finally:
            browser.close()
            logging.info("Browser closed cleanly.")

    return players
