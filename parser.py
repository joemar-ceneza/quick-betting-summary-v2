"""Parses the multi-row-per-round Leo bet-list rows into flat round records.

Same layout as betting-behavior-dashboard: each round spans several scraped rows
(the header row carries the game number; follow-up rows carry the settle time,
the Player score and any side bets). Adds a `product` field (e.g. "Baccarat",
"Dragon Tiger") so the summary can report which products were played.
"""

import logging
import re
from datetime import datetime

import config
import utils


# ======================================================
# PRIVATE HELPERS
# ======================================================
def _split_product_and_table(game_field: str) -> tuple[str, str]:
    """Split a game label like 'Baccarat H22' into ('Baccarat', 'H22').

    The leading alphabetic words form the product name; whatever follows is the
    table id. Returns ('?', '?') pieces when a part cannot be determined.
    """
    tokens = game_field.split()
    product_tokens: list[str] = []
    for token in tokens:
        if token.isalpha():
            product_tokens.append(token)
        else:
            break
    product = " ".join(product_tokens) if product_tokens else "?"
    table = " ".join(tokens[len(product_tokens):]) or "?"
    return product, table


def _reconstruct_winners(games: list[dict]) -> None:
    """Set each round's true winning side from the Banker/Player scores."""
    missing = 0
    for g in games:
        if g["banker"] is None or g["player"] is None:
            g["winner"] = "?"
            missing += 1
        elif g["banker"] > g["player"]:
            g["winner"] = "Banker"
        elif g["player"] > g["banker"]:
            g["winner"] = "Player"
        else:
            g["winner"] = "Tie"
    if missing:
        logging.warning("%d round(s) had no Banker/Player score and were left unscored.", missing)


def _new_round(row: list[str]) -> dict:
    """Build a round record from its header row (the row carrying the game number)."""
    # Cell layout is "GAME ID, GAME, RESULT" (e.g. "83307636, Baccarat G29-1C, Won");
    # the game name is the second-to-last part so a missing game id still parses.
    parts = [part.strip() for part in row[3].split(",")]
    result = parts[-1]
    game_field = parts[-2] if len(parts) >= 2 else "?"
    product, table = _split_product_and_table(game_field)

    bet_field = row[5].strip()
    if "=" in bet_field:
        side, amount = bet_field.split("=", 1)
        side, amount = side.strip(), utils.clean_number(amount)
    else:
        side, amount = bet_field, 0.0

    banker_match = re.search(r"B\s*=\s*(\d+)", row[4])
    return {
        "game": int(row[0]),
        "product": product,
        "table": table,
        "result": result,
        "bet_side": side,
        "bet_amt": amount,
        "turnover": utils.clean_number(row[6]),
        "net": utils.clean_number(row[7]),
        "date": row[1].strip(),
        "time": None,
        "banker": int(banker_match.group(1)) if banker_match else None,
        "player": None,
        "sidebets": [],
    }


def _games_from_rows(rows: list[list[str]]) -> list[dict]:
    """Build round dicts from raw bet-list rows (one game spans several rows)."""
    games: list[dict] = []
    current = None
    for raw in rows:
        row = (list(raw) + [""] * 8)[:8]
        if row[0].strip().isdigit():
            if current:
                games.append(current)
            current = _new_round(row)
        elif current is not None:
            if current["time"] is None and row[1].strip():
                current["time"] = row[1].strip()
            player_match = re.search(r"P\s*=\s*(\d+)", row[4])
            if player_match and current["player"] is None:
                current["player"] = int(player_match.group(1))
            if "=" in row[5]:
                current["sidebets"].append(row[5].strip())
    if current:
        games.append(current)

    _reconstruct_winners(games)
    return games


# ======================================================
# PUBLIC ENTRY POINT
# ======================================================
def parse_rows(rows: list[list[str]]) -> list[dict]:
    """Parse already-extracted bet-list rows (scraped from Leo) into round dicts."""
    games = _games_from_rows(rows)
    logging.info("Parsed %d rounds from %d scraped rows", len(games), len(rows))
    return games


# ======================================================
# ROUND ACCESSORS (shared by summary + conclusion)
# ======================================================
def side_code(side: str) -> str:
    """Map a bet side to B / P / T / O(utside)."""
    return {"Banker": "B", "Player": "P", "Tie": "T"}.get(side, "O")


def round_datetime(game: dict):
    """Return a round's full settle datetime (date + time), or None."""
    try:
        return datetime.strptime(f"{game['date']} {game['time']}", "%m/%d/%Y %I:%M:%S %p")
    except (ValueError, TypeError, KeyError):
        return None


def product_label(game: dict) -> str:
    """Map a round's raw product name to its reporting label.

    Baccarat tables named A-Z (e.g. G29-1C) or 1-9 (e.g. 5 30) are SBO tables,
    so both report as a single "SBO Baccarat" product.
    """
    if game["product"] == "Baccarat" and re.match(r"^([A-Za-z]|[1-9])", game["table"]):
        return config.SBO_BACCARAT_LABEL
    return game["product"]


def stake_per_round(game: dict) -> float:
    """Total amount staked on one round: main wager plus every side bet."""
    stake = game["bet_amt"]
    for sidebet in game["sidebets"]:
        stake += utils.clean_number(sidebet.split("=", 1)[1])
    return stake
