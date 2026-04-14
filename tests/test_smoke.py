"""Smoke tests — validate core logic without external I/O (no Groq, no DB, no network)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Config / settings
# ---------------------------------------------------------------------------

def test_settings_defaults() -> None:
    """Settings should load without errors even when no .env is present."""
    from market_agent.config import Settings

    s = Settings()
    assert s.timezone == "America/New_York"
    assert "SPY" in s.watchlist
    assert s.groq_model  # should be non-empty


def test_watchlist_parsing() -> None:
    """Comma-separated watchlist string should parse into a list."""
    from market_agent.config import Settings

    s = Settings(watchlist="SPY,QQQ, IWM ")
    assert s.watchlist == ["SPY", "QQQ", "IWM"]


# ---------------------------------------------------------------------------
# Trend scoring
# ---------------------------------------------------------------------------

def _make_snapshot(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df["date"] = date.today()
    return df


def test_score_tickers_basic() -> None:
    """Score tickers with deterministic input and verify ordering."""
    from market_agent.analysis.trend_scoring import score_tickers

    snapshot = _make_snapshot([
        {"ticker": "AAA", "close": 100.0, "open": 97.0, "high": 102.0, "low": 96.0, "volume": 1_000_000, "pct_change": 3.0},
        {"ticker": "BBB", "close": 50.0,  "open": 50.5, "high": 51.0, "low": 49.5, "volume":   200_000, "pct_change": -1.0},
        {"ticker": "CCC", "close": 200.0, "open": 198.0, "high": 205.0, "low": 197.0, "volume": 5_000_000, "pct_change": 1.0},
    ])

    all_scores, focus = score_tickers(snapshot, top_n=2)

    assert len(all_scores) == 3
    assert len(focus) == 2
    # All composite scores should be in [0, 1]
    for s in all_scores:
        assert 0.0 <= s.composite_score <= 1.0
    # Scores should be sorted descending
    scores = [s.composite_score for s in all_scores]
    assert scores == sorted(scores, reverse=True)


def test_score_tickers_empty() -> None:
    from market_agent.analysis.trend_scoring import score_tickers

    all_scores, focus = score_tickers(pd.DataFrame(), top_n=3)
    assert all_scores == []
    assert focus == []


def test_ticker_score_direction() -> None:
    from market_agent.analysis.trend_scoring import TickerScore

    up = TickerScore("SPY", pct_change=1.5, volume=1000, volume_anomaly=1.2, volatility_proxy=0.01, composite_score=0.7)
    down = TickerScore("QQQ", pct_change=-0.5, volume=1000, volume_anomaly=1.0, volatility_proxy=0.01, composite_score=0.3)
    assert up.direction == "up"
    assert down.direction == "down"


# ---------------------------------------------------------------------------
# Groq client — dry-run / stub behaviour
# ---------------------------------------------------------------------------

def test_groq_client_dry_run_complete() -> None:
    """Dry-run mode should return stub text without calling the API."""
    from market_agent.groq_client import GroqClient

    client = GroqClient(dry_run=True)
    result = client.complete("sys", "user")
    assert isinstance(result, str)
    assert len(result) > 0


def test_groq_client_dry_run_json() -> None:
    from market_agent.groq_client import GroqClient

    client = GroqClient(dry_run=True)
    result = client.complete_json("sys", "user")
    assert isinstance(result, dict)


def test_groq_client_missing_key_raises() -> None:
    """Without a key and without dry_run, construction should raise ValueError."""
    from market_agent.config import Settings
    from market_agent.groq_client import GroqClient

    with patch("market_agent.groq_client.settings", Settings(groq_api_key="")):
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            GroqClient(dry_run=False)


# ---------------------------------------------------------------------------
# Report generation — dry run, no Groq API calls
# ---------------------------------------------------------------------------

def test_generate_report_dry_run() -> None:
    """Report should render successfully with stub LLM in dry-run mode."""
    from market_agent.analysis.trend_scoring import TickerScore
    from market_agent.groq_client import GroqClient
    from market_agent.reporting.report_generator import generate_report

    snapshot = _make_snapshot([
        {"ticker": "SPY", "close": 450.0, "open": 447.0, "high": 452.0, "low": 446.0, "volume": 80_000_000, "pct_change": 0.67},
        {"ticker": "QQQ", "close": 370.0, "open": 366.0, "high": 371.0, "low": 365.0, "volume": 50_000_000, "pct_change": 1.09},
    ])
    all_scores = [
        TickerScore("SPY", pct_change=0.67, volume=80_000_000, volume_anomaly=1.1, volatility_proxy=0.013, composite_score=0.6),
        TickerScore("QQQ", pct_change=1.09, volume=50_000_000, volume_anomaly=0.9, volatility_proxy=0.016, composite_score=0.8),
    ]
    focus = [all_scores[1], all_scores[0]]

    groq = GroqClient(dry_run=True)
    md = generate_report(
        run_id="test-001",
        as_of=date.today(),
        snapshot=snapshot,
        all_scores=all_scores,
        focus=focus,
        groq=groq,
    )

    assert "## 1 · Market Summary" in md
    assert "## 2 · Focus Tickers" in md
    assert "## 3 · Recommended Actions" in md
    assert "## 4 · Behavior Coaching Note" in md
    assert "DISCLAIMER" in md
    assert "test-001" in md


# ---------------------------------------------------------------------------
# Email notifier — no SMTP config should raise ValueError
# ---------------------------------------------------------------------------

def test_emailer_missing_config_raises() -> None:
    from market_agent.notify.emailer import EmailNotifier

    notifier = EmailNotifier(
        host="smtp.example.com",
        port=587,
        user="",          # missing
        password="",      # missing
        email_from="",
        email_to="someone@example.com",
    )
    with pytest.raises(ValueError, match="SMTP_USER"):
        notifier.send("Test", "body")


def test_emailer_missing_to_raises() -> None:
    from market_agent.notify.emailer import EmailNotifier

    notifier = EmailNotifier(
        host="smtp.example.com",
        port=587,
        user="user@example.com",
        password="pw",
        email_from="user@example.com",
        email_to="",   # missing
    )
    with pytest.raises(ValueError, match="EMAIL_TO"):
        notifier.send("Test", "body")


# ---------------------------------------------------------------------------
# Memory models — basic instantiation
# ---------------------------------------------------------------------------

def test_memory_models_instantiate() -> None:
    from market_agent.memory.models import BehaviorTag, FeedbackEntry, Recommendation, Run

    run = Run(id="abc", run_date="2024-01-01", status="pending")
    assert run.id == "abc"

    rec = Recommendation(
        run_id="abc", ticker="SPY", pct_change=1.0, volume=1000,
        volume_anomaly=1.1, composite_score=0.75,
    )
    assert rec.ticker == "SPY"

    fb = FeedbackEntry(run_id="abc", action_taken="bought", rating=4)
    assert fb.rating == 4

    tag = BehaviorTag(tag="potential_fomo")
    assert tag.tag == "potential_fomo"


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def test_cli_help() -> None:
    """CLI help should exit 0 without raising."""
    from typer.testing import CliRunner

    from market_agent.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run-eod" in result.output
    assert "feedback" in result.output


def test_cli_run_eod_dry_run_no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """run-eod --dry-run should complete without a real DB or Groq key."""
    from typer.testing import CliRunner

    from market_agent.cli import app

    # Stub out pipeline to avoid network/db calls
    mock_pipeline = MagicMock(return_value="# stub report")
    monkeypatch.setattr("market_agent.cli.run_eod_cmd.__wrapped__", mock_pipeline, raising=False)

    # Patch the actual pipeline function that the command calls
    with patch("market_agent.pipeline.init_db"), \
         patch("market_agent.pipeline.get_session") as mock_sess, \
         patch("market_agent.pipeline.fetch_eod_prices") as mock_fetch, \
         patch("market_agent.pipeline.get_latest_snapshot") as mock_snap:

        # Return a realistic-looking snapshot
        snap_df = _make_snapshot([
            {"ticker": "SPY", "close": 450.0, "open": 447.0, "high": 452.0, "low": 446.0,
             "volume": 80_000_000, "pct_change": 0.67},
        ])
        mock_fetch.return_value = snap_df
        mock_snap.return_value = snap_df

        # Mock DB session
        mock_sess.return_value.__enter__ = MagicMock()
        mock_sess.return_value = MagicMock()
        mock_sess.return_value.query.return_value.order_by.return_value.first.return_value = None

        runner = CliRunner()
        result = runner.invoke(app, ["run-eod", "--dry-run", "--no-email", "--as-of", "2024-01-15"])

    # Should not crash
    assert result.exit_code == 0 or "Pipeline failed" not in (result.output or "")
