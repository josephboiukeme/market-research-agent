"""Main EOD pipeline — orchestrates data fetch, scoring, LLM, report, email, and DB logging."""

from __future__ import annotations

import logging
import uuid
from datetime import date

from rich.console import Console
from rich.markdown import Markdown

from market_agent.analysis.trend_scoring import score_tickers
from market_agent.config import settings
from market_agent.data_sources.yfinance_source import fetch_eod_prices, get_latest_snapshot
from market_agent.groq_client import GroqClient
from market_agent.memory.db import get_session, init_db
from market_agent.memory.repository import RecommendationRepository, RunRepository
from market_agent.notify.emailer import EmailNotifier
from market_agent.reporting.report_generator import generate_report

logger = logging.getLogger(__name__)
console = Console()


def run_eod(
    as_of: date | None = None,
    dry_run: bool = False,
    send_email: bool = True,
    top_n: int = 3,
) -> str:
    """Execute the full EOD pipeline.

    Steps:
        1. Fetch market data (yfinance).
        2. Score and rank tickers.
        3. Generate report narrative via Groq LLM (or stub in dry-run mode).
        4. Persist the run and recommendations to Postgres.
        5. Optionally send the report by email.
        6. Return the rendered markdown string.

    Args:
        as_of: Reference trading date (defaults to today).
        dry_run: Skip Groq API calls; use stubbed LLM output.
        send_email: Send the report email after generation.
        top_n: Number of focus tickers to highlight.

    Returns:
        The rendered EOD report as a markdown string.
    """
    if as_of is None:
        as_of = date.today()

    run_id = str(uuid.uuid4())[:8]
    tickers = settings.watchlist

    console.print("\n[bold cyan]Market Research Agent — EOD Run[/bold cyan]")
    console.print(f"  Date     : {as_of}")
    console.print(f"  Tickers  : {', '.join(tickers)}")
    console.print(f"  Dry-run  : {dry_run}")
    console.print(f"  Run ID   : {run_id}\n")

    # ── Ensure DB tables exist ────────────────────────────────────────────────
    try:
        init_db()
    except Exception as exc:
        logger.warning("Could not initialise DB — running without persistence: %s", exc)

    session = None
    run = None
    run_repo = None

    try:
        session = get_session()
        run_repo = RunRepository(session)
        run = run_repo.create(run_id, as_of.isoformat())
    except Exception as exc:
        logger.warning("DB session unavailable — continuing without persistence: %s", exc)

    # ── Step 1: Fetch market data ─────────────────────────────────────────────
    console.print("[bold]1/5[/bold] Fetching market data …")
    try:
        history = fetch_eod_prices(tickers, as_of=as_of, lookback_days=5)
        snapshot = get_latest_snapshot(tickers, as_of=as_of)
    except Exception as exc:
        msg = f"Failed to fetch market data: {exc}"
        logger.error(msg)
        if run and run_repo and session:
            run_repo.mark_failed(run, msg)
            session.close()
        raise

    if snapshot.empty:
        msg = "No market data returned for the watchlist.  The market may be closed."
        console.print(f"[yellow]{msg}[/yellow]")
        if run and run_repo and session:
            run_repo.mark_failed(run, msg)
            session.close()
        return msg

    # ── Step 2: Score and rank ────────────────────────────────────────────────
    console.print("[bold]2/5[/bold] Scoring tickers …")
    all_scores, focus = score_tickers(snapshot, top_n=top_n, history=history)

    # ── Step 3: Generate LLM report ───────────────────────────────────────────
    console.print("[bold]3/5[/bold] Generating report narrative …")
    groq = GroqClient(dry_run=dry_run)
    try:
        report_md = generate_report(
            run_id=run_id,
            as_of=as_of,
            snapshot=snapshot,
            all_scores=all_scores,
            focus=focus,
            groq=groq,
        )
    except Exception as exc:
        msg = f"Report generation failed: {exc}"
        logger.error(msg)
        if run and run_repo and session:
            run_repo.mark_failed(run, msg)
            session.close()
        raise

    # ── Step 4: Persist ───────────────────────────────────────────────────────
    console.print("[bold]4/5[/bold] Persisting run to database …")
    if run and run_repo and session:
        try:
            rec_repo = RecommendationRepository(session)
            rec_repo.save_focus_tickers(run_id, focus)
            run_repo.mark_success(run, report_md)
        except Exception as exc:
            logger.warning("DB persistence failed (non-fatal): %s", exc)
        finally:
            session.close()

    # ── Step 5: Send email ────────────────────────────────────────────────────
    if send_email and not dry_run:
        console.print("[bold]5/5[/bold] Sending email …")
        try:
            notifier = EmailNotifier()
            notifier.send(
                subject=f"📊 Market Research Agent — EOD Report {as_of}",
                body_markdown=report_md,
            )
            console.print("[green]✓ Email sent.[/green]")
        except Exception as exc:
            logger.warning("Email delivery failed (non-fatal): %s", exc)
            console.print(f"[yellow]⚠ Email skipped: {exc}[/yellow]")
    else:
        console.print("[bold]5/5[/bold] Email skipped (dry-run or send_email=False).")

    # ── Render to terminal ────────────────────────────────────────────────────
    console.print("\n[bold green]── EOD Report ──────────────────────────────[/bold green]")
    console.print(Markdown(report_md))

    return report_md
