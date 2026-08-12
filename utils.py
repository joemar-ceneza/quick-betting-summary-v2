"""Generic, reusable helpers with no project-specific knowledge."""

import logging
import time
from typing import Any
from typing import Callable


def retry(func: Callable, retries: int = 3, delay: int = 2) -> Any:
    """Retry a callable up to `retries` times, sleeping `delay` seconds between attempts."""
    for attempt in range(retries):
        try:
            return func()
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} of {retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    raise Exception(f"All {retries} retry attempts failed")


def distinct_in_order(values: list[str]) -> list[str]:
    """Return the distinct non-empty values preserving first-seen order."""
    seen: list[str] = []
    for value in values:
        if value and value != "?" and value not in seen:
            seen.append(value)
    return seen


def clean_number(value: str) -> float:
    """Convert a messy currency string to float (commas/quotes/blank safe)."""
    if value is None:
        return 0.0
    cleaned = value.replace(",", "").replace('"', "").strip()
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ======================================================
# PLAYWRIGHT HELPERS
# ======================================================
def get_frame(page: Any, name: str, retries: int = 20) -> Any:
    """Poll page.frames until a frame named `name` is found, or raise RuntimeError."""
    for _ in range(retries):
        for frame in page.frames:
            if frame.name == name:
                return frame
        page.wait_for_timeout(500)
    raise RuntimeError(f"Frame '{name}' not found after {retries} attempts")


def handle_dialog(dialog: Any) -> None:
    """Accept any browser dialog automatically."""
    dialog.accept()


def click_with_retry(locator: Any, retries: int = 3) -> None:
    """Click a Playwright locator, retrying on failure up to `retries` times."""
    for attempt in range(retries):
        try:
            locator.click()
            return
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            logging.warning("Click failed (attempt %d/%d): %s. Retrying...", attempt + 1, retries, e)
