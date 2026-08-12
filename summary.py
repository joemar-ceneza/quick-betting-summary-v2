"""Builds the quick-summary record for each scraped player.

Takes the raw dicts produced by scraper.run_scraper(), parses the bet-list rows
into rounds (parser.parse_rows) and computes every requested field plus the
conclusion verdict. Any field that cannot be computed is returned as "-" / None
instead of failing the run. Results are rendered by ui.py — nothing is written
to disk.
"""

import logging

import config
import conclusion
import parser
import utils


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


def _build_summary(player: dict, report_date: str) -> dict:
    """Compute the full quick-summary record for one scraped player."""
    games = parser.parse_rows(player["rows"]) if player["rows"] else []

    won = sum(1 for g in games if g["result"] == "Won")
    lose = sum(1 for g in games if g["result"] == "Lose")
    draw = len(games) - won - lose
    decided = won + lose

    nets = [g["net"] for g in games]
    stakes = [parser.stake_per_round(g) for g in games]
    biggest_win = max((x for x in nets if x > 0), default=None)
    biggest_loss = min((x for x in nets if x < 0), default=None)

    return {
        "Date": report_date,
        "Username": player["username"],
        "Currency": player["currency"],
        "Status": player["status"],
        "Table Limit": player["table_limit"],
        "Products Played": ", ".join(utils.distinct_in_order([parser.product_label(g) for g in games])),
        "Total Rounds Played": len(games),
        "Total Won": won,
        "Total Lose": lose,
        "Total Draw": draw,
        "Total Member Win/Loss": round(sum(nets), 2) if games else None,
        "Winning Percentage": round(won / decided * 100, 1) if decided else None,
        "Max Stake per Round": max(stakes) if stakes else None,
        "Biggest Winning Amount": biggest_win,
        "Biggest Losing Amount": biggest_loss,
        "Betting Options Placed": ", ".join(_betting_options(games)),
        "Betting Pattern": "",
        "Conclusion": conclusion.build_conclusion(),
    }


# ======================================================
# PUBLIC ENTRY POINT
# ======================================================
def build_summaries(players: list[dict], report_date: str) -> list[dict]:
    """Build one quick-summary record per scraped player."""
    summaries: list[dict] = []
    for player in players:
        record = _build_summary(player, report_date)
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
