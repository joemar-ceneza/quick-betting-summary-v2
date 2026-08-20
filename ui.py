"""Presentation layer for the Quick Summary report (Streamlit).

Renders the summary records built by summary.build_summaries() as player cards
in the browser. Public entry points: inject_theme() and render_summaries().
"""

import streamlit as st

import config


# ======================================================
# TOKEN / FORMAT HELPERS
# ======================================================
def _c(hex_color: str) -> str:
    """'RRGGBB' -> '#RRGGBB'."""
    return "#" + hex_color


def _rgba(hex_color: str, alpha: float) -> str:
    """'RRGGBB' -> 'rgba(r,g,b,alpha)' for soft translucent backgrounds."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _fmt_num(value, signed: bool = False, decimals: int = 0) -> str:
    """Format a number for display; None becomes an em dash."""
    if value is None:
        return "—"
    fmt = f"{{value:+,.{decimals}f}}" if signed else f"{{value:,.{decimals}f}}"
    return fmt.format(value=value)


def _fmt_pct(value) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _fmt_text(value: str) -> str:
    return value if value and value != "-" else "—"


def _status_theme(status: str) -> tuple[str, str]:
    """(text_color, soft_bg) CSS values for an account status badge."""
    return {
        "Active": ("var(--success)", "var(--success-soft)"),
        "Suspended": ("var(--warning)", "var(--warning-soft)"),
        "Closed": ("var(--danger)", "var(--danger-soft)"),
    }.get(status, ("inherit", "var(--panel2)"))


def _winloss_class(value) -> str:
    if value is None:
        return ""
    return "pos" if value >= 0 else "neg"


def _delta_badge(delta) -> str:
    """▲/▼ change badge vs the previous day; empty when there's no previous day."""
    if delta is None:
        return ""
    if delta > 0:
        return f"<span class='qs-dup'>▲ {delta:+,.0f}</span>"
    if delta < 0:
        return f"<span class='qs-ddown'>▼ {delta:+,.0f}</span>"
    return "<span class='qs-dup'>± 0</span>"


def _daily_html(record: dict) -> str:
    """HTML for the Day-by-Day Comparison table (empty string when no data)."""
    daily = record.get("Daily") or []
    if not daily:
        return ""
    body = ""
    for d in daily:
        rounds = f"{d['rounds']:,.0f}" if d["rounds"] else "0"
        body += (
            "<tr>"
            f"<td class='qs-ddate'>{d['date']}</td>"
            f"<td>{rounds}{_delta_badge(d.get('rounds_delta'))}</td>"
            f"<td>{_fmt_num(d['won'])}</td>"
            f"<td>{_fmt_num(d['lose'])}</td>"
            f"<td>{_fmt_num(d['draw'])}</td>"
            f"<td class='{_winloss_class(d['net'])}'>{_fmt_num(d['net'], signed=True)}{_delta_badge(d.get('net_delta'))}</td>"
            f"<td>{_fmt_pct(d['win_pct'])}</td>"
            f"<td>{_fmt_num(d['max_stake'])}</td>"
            "</tr>"
        )
    return (
        "<div class='qs-daily'>"
        "<div class='qs-daily-title'>Day-by-Day Comparison</div>"
        "<table class='qs-table'>"
        "<thead><tr>"
        "<th>Date</th><th>Rounds Played</th><th>Won</th><th>Lose</th><th>Draw</th>"
        "<th>Member Win/Loss</th><th>Win %</th><th>Max Stake</th>"
        "</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>"
    )


# ======================================================
# THEME (CSS)
# ======================================================
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family:'Inter',-apple-system,'Segoe UI',sans-serif; }
header[data-testid="stHeader"] { background: transparent !important; }
footer { display: none !important; }
.block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1200px; }

.qs-header { margin-bottom:18px; background:var(--panel); border:1px solid var(--line); border-radius:14px;
  padding:14px 20px; display:flex; align-items:center; gap:14px; }
.qs-title { font-weight:800; font-size:19px; letter-spacing:-.01em; }
.qs-chip { display:inline-flex; align-items:center; gap:6px; padding:5px 12px; background:var(--panel2);
  border:1px solid var(--line); border-radius:999px; font-size:12.5px; opacity:.85; }
.qs-chip b { opacity:1; }
.qs-spacer { flex:1; }

.qs-card { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px 20px;
  margin-bottom:16px; }
.qs-card-head { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
.qs-user { font-size:17px; font-weight:800; letter-spacing:-.01em; }
.qs-user .userlabel { font-size:13px; font-weight:600; opacity:.65; margin-right:2px; }
.qs-badge { padding:4px 12px; border-radius:999px; font-weight:700; font-size:12.5px; }

.qs-kpis { display:grid; grid-template-columns:repeat(6, 1fr); gap:10px; margin-bottom:12px; }
.qs-kpi { background:var(--panel2); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
.qs-kpi .label { font-size:11.5px; font-weight:500; opacity:.65; }
.qs-kpi .value { font-size:20px; font-weight:800; letter-spacing:-.02em; margin-top:6px; }
.qs-kpi .value.pos { color:var(--success); } .qs-kpi .value.neg { color:var(--danger); }

.qs-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-bottom:12px; }
.qs-cell { background:var(--panel2); border:1px solid var(--line); border-radius:10px; padding:10px 14px; }
.qs-cell .label { font-size:11.5px; font-weight:500; opacity:.65; }
.qs-cell .val { font-size:14px; font-weight:600; margin-top:4px; }
.qs-cell .val.pos { color:var(--success); } .qs-cell .val.neg { color:var(--danger); }
.qs-wide { grid-template-columns:1fr; margin-bottom:0; }
.qs-wide .qs-cell { margin-bottom:8px; }

.qs-landing { max-width:560px; margin-top:8px; padding:22px 26px; background:var(--panel);
  border:1px solid var(--line); border-radius:12px; }
.qs-landing .head { font-size:16px; font-weight:700; }
.qs-landing .body { opacity:.85; margin-top:8px; line-height:1.6; }

/* Editable Betting Pattern / Conclusion inputs — match the card panels.
   Base rule = fixed 100px box (Betting Pattern keeps this). */
div[data-testid="stTextArea"] > div { gap:4px; }
div[data-testid="stTextArea"] label p { font-size:11.5px; font-weight:600; opacity:.65; letter-spacing:.01em; }
div[data-testid="stTextArea"] textarea {
  background-color: var(--panel2) !important;
  border:1px solid var(--line) !important;
  border-radius:10px !important;
  color:inherit !important;
  font-family:inherit !important;
  font-size:14px !important;
  font-weight:600 !important;
  line-height:1.5 !important;
  padding:10px 14px !important;
  height:100px !important;
  min-height:100px !important;
  max-height:100px !important;
  overflow-y:auto !important;   /* long text scrolls inside the fixed box */
  resize:none !important;
}
div[data-testid="stTextArea"] textarea:focus {
  border-color: var(--panel2) !important;
  box-shadow:0 0 0 1px var(--line) inset !important;
}
div[data-testid="stTextArea"] textarea::placeholder { color:inherit !important; opacity:.4 !important; font-weight:500 !important; }

/* Conclusion only: grow taller with its content (key-scoped, Streamlit >= 1.39) */
div[class*="st-key-concl_"] textarea {
  field-sizing: content;
  height:auto !important;
  min-height:100px !important;
  max-height:none !important;
  overflow-y:hidden !important;
  resize:vertical !important;
}

/* Player card = a bordered container so the Betting Pattern / Conclusion
   inputs live inside the same main box as the stats */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 16px;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {
  gap: 12px;
}

/* Day-by-Day Comparison table */
.qs-daily { margin-top: 2px; }
.qs-daily-title { font-size: 13px; font-weight: 800; letter-spacing:-.01em; margin-bottom: 8px; opacity:.9; }
.qs-table { width:100%; border-collapse: collapse; font-size: 12.5px; }
.qs-table th { text-align:left; padding:8px 10px; font-size:11px; font-weight:600; opacity:.6;
  border-bottom:1px solid var(--line); white-space:nowrap; }
.qs-table td { padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
.qs-table tr:last-child td { border-bottom:none; }
.qs-table td.pos { color:var(--success); } .qs-table td.neg { color:var(--danger); }
.qs-ddate { font-weight:700; }
.qs-dup { color:var(--success); font-size:11px; margin-left:5px; font-weight:700; }
.qs-ddown { color:var(--danger); font-size:11px; margin-left:5px; font-weight:700; }
"""


def inject_theme() -> None:
    """Public: apply the shared font + design tokens; follows Streamlit's light/dark theme."""
    root_vars = (
        f"--success:{_c(config.T_SUCCESS)};--success-soft:{_rgba(config.T_SUCCESS, 0.16)};"
        f"--warning:{_c(config.T_WARNING)};--warning-soft:{_rgba(config.T_WARNING, 0.16)};"
        f"--danger:{_c(config.T_DANGER)};--danger-soft:{_rgba(config.T_DANGER, 0.16)};"
        f"--panel:{_rgba(config.T_NEUTRAL, 0.07)};--panel2:{_rgba(config.T_NEUTRAL, 0.10)};"
        f"--line:{_rgba(config.T_NEUTRAL, 0.25)};"
    )
    st.markdown(f"<style>:root{{{root_vars}}}{_CSS}</style>", unsafe_allow_html=True)


# ======================================================
# SECTIONS
# ======================================================
def _render_header(summaries: list[dict]) -> None:
    """Render the report header with the date extracted from the first summary."""
    report_date = summaries[0]["Date"] if summaries else "—"
    st.markdown(
        "<div class='qs-header'>"
        "<span class='qs-title'>🎴 Quick Summary Report</span>"
        "<span class='qs-spacer'></span>"
        f"<span class='qs-chip'>Report Date: <b>{report_date}</b></span>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_player_card(record: dict) -> None:
    """Render an individual player's summary card."""
    status = record["Status"]
    status_color, status_bg = _status_theme(status)
    winloss = record["Total Member Win/Loss"]
    wl_class = _winloss_class(winloss)

    # Sanitize username to ensure safe Streamlit widget keys (no spaces/special chars)
    safe_username = str(record.get("Username", "unknown")).replace(" ", "_").replace("@", "_")

    kpis = [
        ("Total Rounds Played", _fmt_num(record["Total Rounds Played"]), ""),
        ("Total Won", _fmt_num(record["Total Won"]), ""),
        ("Total Lose", _fmt_num(record["Total Lose"]), ""),
        ("Total Draw", _fmt_num(record["Total Draw"]), ""),
        ("Winning Percentage", _fmt_pct(record["Winning Percentage"]), ""),
        ("Member Win/Loss", _fmt_num(winloss, signed=True), wl_class),
    ]
    kpi_html = "".join(
        f"<div class='qs-kpi'><div class='label'>{label}</div><div class='value {css}'>{value}</div></div>"
        for label, value, css in kpis
    )

    cells = [
        ("Max Stake per Round", _fmt_num(record["Max Stake per Round"]), ""),
        (
            "Biggest Winning Amount",
            _fmt_num(record["Biggest Winning Amount"], signed=True),
            _winloss_class(record["Biggest Winning Amount"]),
        ),
        (
            "Biggest Losing Amount",
            _fmt_num(record["Biggest Losing Amount"], signed=True),
            _winloss_class(record["Biggest Losing Amount"]),
        ),
    ]
    cell_html = "".join(
        f"<div class='qs-cell'><div class='label'>{label}</div><div class='val {css}'>{value}</div></div>"
        for label, value, css in cells
    )

    wide_rows = [
        ("Products Played", _fmt_text(record["Products Played"])),
        ("Betting Options Placed", _fmt_text(record["Betting Options Placed"])),
    ]
    wide_html = "".join(
        f"<div class='qs-cell'><div class='label'>{label}</div><div class='val'>{value}</div></div>"
        for label, value in wide_rows
    )

    with st.container(border=True):
        st.markdown(
            "<div class='qs-card-head'>"
            f"<span class='qs-user'><span class='userlabel'>Username:</span> {record['Username']}</span>"
            f"<span class='qs-badge' style='color:{status_color};background:{status_bg}'>{_fmt_text(status)}</span>"
            f"<span class='qs-chip'>Currency <b>{_fmt_text(record['Currency'])}</b></span>"
            f"<span class='qs-chip'>Table Limit <b>{_fmt_text(record['Table Limit'])}</b></span>"
            "<span class='qs-spacer'></span>"
            f"<span class='qs-chip'>Date <b>{record['Date']}</b></span>"
            "</div>"
            f"<div class='qs-kpis'>{kpi_html}</div>"
            f"<div class='qs-grid'>{cell_html}</div>"
            f"<div class='qs-grid qs-wide'>{wide_html}</div>",
            unsafe_allow_html=True,
        )

        # User-editable fields (Betting Pattern = fixed box, Conclusion = auto-grow)
        st.text_area(
            "Betting Pattern",
            value=record.get("Betting Pattern", ""),
            key=f"bp_{safe_username}",
            placeholder="Type the betting pattern here...",
        )
        st.text_area(
            "Conclusion",
            value=record.get("Conclusion", "Normal"),
            key=f"concl_{safe_username}",
            placeholder="Type the conclusion here...",
        )

    # Day-by-Day Comparison — separate collapsible section below the summary
    daily_html = _daily_html(record)
    if daily_html:
        with st.expander(" Day-by-Day Comparison"):
            st.markdown(daily_html, unsafe_allow_html=True)


# ======================================================
# PUBLIC ENTRY POINTS
# ======================================================
def render_landing() -> None:
    """Render the pre-scrape landing card explaining how to start."""
    st.title("🎴 Quick Summary Report")
    st.markdown(
        "<div class='qs-landing'><div class='head'>Start a quick summary</div>"
        "<div class='body'>Enter a <b>username</b> and a <b>date range</b> in the sidebar, then click "
        "<b>Scrape &amp; Summarize</b>. The report pulls the player's account details and bet list "
        "from Leo and shows the full quick summary here in the browser.</div></div>",
        unsafe_allow_html=True,
    )


def render_summaries(summaries: list[dict]) -> None:
    """Render the full quick-summary report: header and player cards."""
    _render_header(summaries)
    for record in summaries:
        _render_player_card(record)
