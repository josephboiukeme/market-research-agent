"""EOD report generator — assembles the Jinja2 template with live data and LLM narrative."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from market_agent.analysis.trend_scoring import TickerScore
from market_agent.config import settings
from market_agent.groq_client import GroqClient

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a concise, data-driven market analyst assistant.
Write in plain markdown.
Do NOT include headers — only prose for the section assigned to you.
Do NOT provide specific buy/sell prices or guarantees of returns.
Always end with a reminder that this is not financial advice.
Keep each response under 200 words.
"""


def _render_template(context: dict) -> str:
    """Render the Jinja2 EOD template."""
    template_dir = Path(__file__).parent
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("eod_template.md.j2")
    return tpl.render(**context)


def _focus_summary_text(focus: list[TickerScore], snapshot: pd.DataFrame) -> str:
    """Build a compact text summary of focus tickers to pass to the LLM."""
    lines = []
    snap_idx = snapshot.set_index("ticker")
    for s in focus:
        close = snap_idx.at[s.ticker, "close"] if s.ticker in snap_idx.index else 0.0
        lines.append(
            f"{s.ticker}: close={close:.2f}, daily={s.pct_change:+.2f}%, "
            f"vol_anomaly={s.volume_anomaly:.2f}x, score={s.composite_score:.3f}"
        )
    return "\n".join(lines)


def generate_report(
    run_id: str,
    as_of: date,
    snapshot: pd.DataFrame,
    all_scores: list[TickerScore],
    focus: list[TickerScore],
    groq: GroqClient,
) -> str:
    """Generate the full EOD markdown report.

    Args:
        run_id: Unique identifier for this pipeline run (stored in DB).
        as_of: The reference trading date.
        snapshot: Latest-session DataFrame (one row per ticker).
        all_scores: All scored tickers sorted by composite score descending.
        focus: Top-N focus tickers.
        groq: Configured GroqClient instance.

    Returns:
        The rendered markdown string.
    """
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz)
    snap_idx = snapshot.set_index("ticker")

    # Enrich focus tickers with close price for template rendering
    class _FocusRow:
        def __init__(self, s: TickerScore, close: float) -> None:
            self.ticker = s.ticker
            self.close = close
            self.pct_change = s.pct_change
            self.volume = s.volume
            self.volume_anomaly = s.volume_anomaly
            self.composite_score = s.composite_score

    focus_rows = [
        _FocusRow(
            s,
            close=float(snap_idx.at[s.ticker, "close"]) if s.ticker in snap_idx.index else 0.0,
        )
        for s in focus
    ]

    focus_text = _focus_summary_text(focus, snapshot)

    # --- LLM sections --------------------------------------------------------
    market_summary = groq.complete(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=(
            f"Date: {as_of}\n"
            f"Watchlist snapshot (all tickers, sorted by score):\n"
            + "\n".join(
                f"  {s.ticker}: {s.pct_change:+.2f}% | score={s.composite_score:.3f}"
                for s in all_scores
            )
            + "\n\nWrite the 'Market Summary' section of an EOD report (2-3 sentences)."
        ),
    )

    recommendations = groq.complete(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=(
            f"Date: {as_of}\n"
            f"Focus tickers:\n{focus_text}\n\n"
            "Write the 'Recommended Actions for Next Morning' section as a numbered list "
            "(3-5 actionable but cautious observations — no specific price targets)."
        ),
    )

    coaching_note = groq.complete(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=(
            f"Date: {as_of}\n"
            f"Focus tickers:\n{focus_text}\n\n"
            "Write a short 'Behavior Coaching Note' (2-3 sentences) reminding the reader "
            "to avoid common emotional biases such as FOMO, overtrading, or panic selling."
        ),
    )

    context = {
        "report_date": as_of.isoformat(),
        "generated_at": now_local.strftime("%Y-%m-%d %H:%M"),
        "timezone": settings.timezone,
        "run_id": run_id,
        "market_summary": market_summary.strip(),
        "focus_tickers": focus_rows,
        "recommendations": recommendations.strip(),
        "coaching_note": coaching_note.strip(),
    }

    return _render_template(context)
