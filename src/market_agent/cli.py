"""CLI entry-point (Typer).

Commands:
    market-agent run-eod [--as-of YYYY-MM-DD] [--dry-run] [--no-email] [--output PATH]
    market-agent db init
    market-agent feedback [--run-id RUN_ID] [--ticker TICKER]
                          [--action ACTION] [--rating 1-5] [--notes NOTES]
"""

import logging
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="market-agent",
    help="Agentic market research assistant — Groq + SMTP + Postgres + cron.",
    add_completion=False,
)
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ── run-eod ──────────────────────────────────────────────────────────────────

@app.command("run-eod")
def run_eod_cmd(
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Reference date in YYYY-MM-DD format (defaults to today).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Skip Groq API calls and use stubbed LLM output.",
    ),
    no_email: bool = typer.Option(
        False,
        "--no-email",
        help="Generate the report but do not send an email.",
    ),
    top_n: int = typer.Option(
        3,
        "--top-n",
        help="Number of focus tickers to highlight in the report.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Write the markdown report to this file path (in addition to printing it).",
    ),
) -> None:
    """Run the end-of-day market research pipeline."""
    from market_agent.pipeline import run_eod

    ref_date: date | None = None
    if as_of:
        try:
            ref_date = date.fromisoformat(as_of)
        except ValueError:
            console.print(f"[red]Invalid date format: '{as_of}'.  Use YYYY-MM-DD.[/red]")
            raise typer.Exit(1)

    try:
        report_md = run_eod(
            as_of=ref_date,
            dry_run=dry_run,
            send_email=not no_email,
            top_n=top_n,
        )
    except Exception as exc:
        console.print(f"[bold red]Pipeline failed:[/bold red] {exc}")
        logging.exception("Unhandled pipeline error")
        raise typer.Exit(1)

    if output and report_md:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_md, encoding="utf-8")
        console.print(f"[green]✓ Report saved to {output}[/green]")


# ── db ────────────────────────────────────────────────────────────────────────

db_app = typer.Typer(help="Database management commands.")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init_cmd() -> None:
    """Create all database tables (idempotent)."""
    from market_agent.memory.db import init_db

    console.print("Initialising database …")
    try:
        init_db()
        console.print("[green]✓ Database tables created (or already exist).[/green]")
    except Exception as exc:
        console.print(f"[red]DB init failed: {exc}[/red]")
        raise typer.Exit(1)


# ── feedback ──────────────────────────────────────────────────────────────────

@app.command("feedback")
def feedback_cmd(
    run_id: str | None = typer.Option(
        None,
        "--run-id",
        help="Run ID to attach feedback to (defaults to the most recent run).",
    ),
    ticker: str | None = typer.Option(None, "--ticker", help="Ticker the action relates to."),
    action: str | None = typer.Option(
        None, "--action", help="What you actually did (e.g. 'bought SPY', 'held', 'sold QQQ')."
    ),
    rating: int | None = typer.Option(
        None,
        "--rating",
        help="Satisfaction rating 1-5 for the recommendation quality.",
        min=1,
        max=5,
    ),
    notes: str | None = typer.Option(None, "--notes", help="Any additional notes."),
) -> None:
    """Record what you did after reviewing the EOD report."""
    from market_agent.memory.db import get_session
    from market_agent.memory.repository import FeedbackRepository, RunRepository

    session = get_session()
    try:
        run_repo = RunRepository(session)
        if run_id:
            target_run = run_repo.get_by_id(run_id)
            if not target_run:
                console.print(f"[red]No run found with ID '{run_id}'.[/red]")
                raise typer.Exit(1)
        else:
            target_run = run_repo.get_latest()
            if not target_run:
                console.print("[red]No runs in the database yet.  Run 'market-agent run-eod' first.[/red]")
                raise typer.Exit(1)
            console.print(f"Using most recent run: [cyan]{target_run.id}[/cyan] ({target_run.run_date})")

        fb_repo = FeedbackRepository(session)
        entry = fb_repo.record(
            run_id=target_run.id,
            action_taken=action,
            ticker=ticker.upper() if ticker else None,
            rating=rating,
            notes=notes,
        )

        table = Table(title="Feedback Recorded", show_header=False)
        table.add_row("Run ID", target_run.id)
        table.add_row("Ticker", entry.ticker or "—")
        table.add_row("Action", entry.action_taken or "—")
        table.add_row("Rating", str(entry.rating) if entry.rating else "—")
        table.add_row("Notes", entry.notes or "—")
        console.print(table)
        console.print("[green]✓ Feedback saved.[/green]")
    finally:
        session.close()


if __name__ == "__main__":
    app()
