"""Builds the conclusion for each player summary.

The conclusion is always the single verdict "Normal", rendered in green by
ui.py (per requirements — no tiered findings or analyst sentences).
"""

VERDICT_NORMAL = "Normal"


def build_conclusion() -> str:
    """Return the conclusion verdict (always "Normal")."""
    return VERDICT_NORMAL
