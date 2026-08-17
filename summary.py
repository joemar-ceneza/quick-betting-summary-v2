"""Builds the quick-summary record for each scraped player.

Takes the raw dicts produced by scraper.run_scraper(), parses the bet-list rows
into rounds (parser.parse_rows) and computes every requested field plus the
conclusion verdict. Any field that cannot be computed is returned as "-" / None
instead of failing the run. Results are rendered by ui.py — nothing is written
to disk.
"""

import logging
from datetime import date, datetime, timedelta

import config
import conclusion
import parser
import utils


# ======================================================
# DAY-BY-DAY COMPARISON
# ======================================================
def _parse_round_date(game: dict):
    """A round's settle day as a date, or None when it cannot be read."""
    try:
        return datetime.strptime(game["date"], "%m/%d/%Y").date()
    except (ValueError, TypeError, KeyError):
        return None


def _daily_breakdown(games: list[dict], from_date=None, to_date=None) -> list[dict]:
    """One row per date in [from_date .. to_date], with deltas vs the previous day.

    When from/to are None (CLI runs) the range is derived from the round dates
    themselves. Days with no bets are zero-filled so the table always covers the
    full window.
    """
    if from_date is None or to_date is None:
        round_dates = [d for d in (_parse_round_date(g) for g in games) if d]
        if not round_dates:
            return []
        from_date, to_date = min(round_dates), max(round_dates)

    per_day: dict[date, dict] = {}
    for g in games:
        d = _parse_round_date(g)
        if d is None:
            continue
        day = per_day.setdefault(d, {"won": 0, "lose": 0, "nets": [], "stakes": []})
        if g["result"] == "Won":
            day["won"] += 1
        elif g["result"] == "Lose":
            day["lose"] += 1
        day["nets"].append(g["net"])
        day["stakes"].append(parser.stake_per_round(g))

    rows: list[dict] = []
    prev = None
    cursor = from_date
    while cursor <= to_date:
        day = per_day.get(cursor)
        won = day["won"] if day else 0
        lose = day["lose"] if day else 0
        nets = day["nets"] if day else []
        stakes = day["stakes"] if day else []
        rounds = len(nets)
        if rounds == 0:
            cursor += timedelta(days=1)
            continue  # hide days with no bets — only show days that were played
        date_label = cursor.strftime("%m/%d/%Y")
        cursor += timedelta(days=1)
        draw = rounds - won - lose
        decided = won + lose
        net = round(sum(nets), 2)

        row = {
            "date": date_label,
            "rounds": rounds,
            "won": won,
            "lose": lose,
            "draw": draw,
            "net": net,
            "win_pct": round(won / decided * 100, 1) if decided else None,
            "max_stake": max(stakes) if stakes else None,
            "biggest_win": max((x for x in nets if x > 0), default=None),
            "biggest_loss": min((x for x in nets if x < 0), default=None),
            "rounds_delta": (rounds - prev["rounds"]) if prev else None,
            "net_delta": (net - prev["net"]) if prev else None,
        }
        rows.append(row)
        prev = row
    return rows


# ======================================================
# SUMMARY RECORD
# ======================================================
def _betting_options(games: list[dict]) -> list[str]:
    """Every distinct wager the player placed (main sides + side bets)."""
    options: list[str] = []
    for g in games:
        options.append(g["bet_side"])
        for sidebet in g["sidebets"]:
            options.append(sidebet.split("=", 1)[0].strip())
    return utils.distinct_in_order(options)


def _build_summary(player: dict, report_date: str, from_date=None, to_date=None) -> dict:
    """Compute the full quick-summary record for one scraped player.

    The main summary always reflects the selected [from_date .. to_date] range.
    The day-by-day comparison ignores the From date and automatically covers the
    8 days ending on the To date (independent of the selected range).
    """
    games = parser.parse_rows(player["rows"]) if player["rows"] else []

    if from_date and to_date:
        summary_games = [g for g in games if (d := _parse_round_date(g)) and from_date <= d <= to_date]
        daily_from = to_date - timedelta(days=7)
        daily_games = [g for g in games if (d := _parse_round_date(g)) and daily_from <= d <= to_date]
        daily = _daily_breakdown(daily_games, daily_from, to_date)
    else:
        summary_games = games
        daily = _daily_breakdown(games, None, None)

    won = sum(1 for g in summary_games if g["result"] == "Won")
    lose = sum(1 for g in summary_games if g["result"] == "Lose")
    draw = len(summary_games) - won - lose
    decided = won + lose

    nets = [g["net"] for g in summary_games]
    stakes = [parser.stake_per_round(g) for g in summary_games]
    biggest_win = max((x for x in nets if x > 0), default=None)
    biggest_loss = min((x for x in nets if x < 0), default=None)

    return {
        "Date": report_date,
        "Username": player["username"],
        "Currency": player["currency"],
        "Status": player["status"],
        "Table Limit": player["table_limit"],
        "Products Played": ", ".join(utils.distinct_in_order([parser.product_label(g) for g in summary_games])),
        "Total Rounds Played": len(summary_games),
        "Total Won": won,
        "Total Lose": lose,
        "Total Draw": draw,
        "Total Member Win/Loss": round(sum(nets), 2) if summary_games else None,
        "Winning Percentage": round(won / decided * 100, 1) if decided else None,
        "Max Stake per Round": max(stakes) if stakes else None,
        "Biggest Winning Amount": biggest_win,
        "Biggest Losing Amount": biggest_loss,
        "Betting Options Placed": ", ".join(_betting_options(summary_games)),
        "Betting Pattern": "",
        "Conclusion": conclusion.build_conclusion(),
        "Daily": daily,
    }


# ======================================================
# PUBLIC ENTRY POINT
# ======================================================
def build_summaries(players: list[dict], report_date: str, from_date=None, to_date=None) -> list[dict]:
    """Build one quick-summary record per scraped player."""
    summaries: list[dict] = []
    for player in players:
        record = _build_summary(player, report_date, from_date, to_date)
        summaries.append(record)
        logging.info(
            "Summary — %s: %s rounds | W/L/D %s/%s/%s | net %s | pattern: %s | conclusion: %s",
            record["Username"],
            record["Total Rounds Played"],
            record["Total Won"],
            record["Total Lose"],
            record["Total Draw"],
            record["Total Member Win/Loss"],
            record["Betting Pattern"] or "-",
            record["Conclusion"],
        )
    return summaries
