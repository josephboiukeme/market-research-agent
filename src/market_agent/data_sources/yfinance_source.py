"""yfinance-backed market data source.

yfinance is an *unofficial* wrapper around Yahoo Finance.
- It is free and requires no API key.
- Usage is subject to Yahoo's terms of service.
- For production use, consider a paid data provider (e.g. Polygon, Alpaca).

Install:  pip install yfinance
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def fetch_eod_prices(
    tickers: list[str],
    as_of: date | None = None,
    lookback_days: int = 5,
) -> pd.DataFrame:
    """Fetch end-of-day OHLCV data for *tickers* using yfinance.

    Returns a DataFrame with columns:
        ticker, date, open, high, low, close, volume, pct_change

    The *pct_change* column reflects the single-day % change for the most
    recent session (i.e. close vs. prior close).

    Args:
        tickers: List of ticker symbols (e.g. ["SPY", "QQQ"]).
        as_of: Reference date (defaults to today).  Useful for back-testing.
        lookback_days: Trading days of history to download (need at least 2 to
            compute pct_change reliably).

    Returns:
        DataFrame sorted by date ascending, one row per (ticker, date).
    """
    try:
        import yfinance as yf  # optional dependency
    except ImportError as exc:
        raise ImportError(
            "yfinance is required for market data.  "
            "Install it with:  pip install yfinance"
        ) from exc

    if as_of is None:
        as_of = date.today()

    # Download a window so we have enough history for pct_change
    end = as_of + timedelta(days=1)  # yfinance end is exclusive
    start = as_of - timedelta(days=lookback_days * 2)  # extra buffer for weekends/holidays

    logger.info("Fetching yfinance data for %s (start=%s, end=%s)", tickers, start, end)

    raw = yf.download(
        tickers=tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if raw.empty:
        logger.warning("yfinance returned no data for %s", tickers)
        return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "volume", "pct_change"])

    # yfinance returns multi-level columns when multiple tickers are requested
    records: list[dict] = []

    # Normalise: always work with a MultiIndex columns frame
    if len(tickers) == 1:
        # Single-ticker: columns are flat ('Open', 'Close', …)
        df = raw.copy()
        df.columns = [c.lower() for c in df.columns]
        df["ticker"] = tickers[0].upper()
        df["date"] = df.index.date
        df["pct_change"] = df["close"].pct_change() * 100
        for _, row in df.iterrows():
            records.append(_row_to_record(row, row["ticker"]))
    else:
        for ticker in tickers:
            try:
                df = raw.xs(ticker, axis=1, level=1).copy()
            except KeyError:
                logger.warning("No data returned for %s — skipping.", ticker)
                continue
            df.columns = [c.lower() for c in df.columns]
            df["ticker"] = ticker.upper()
            df["date"] = df.index.date
            df["pct_change"] = df["close"].pct_change() * 100
            for _, row in df.iterrows():
                records.append(_row_to_record(row, ticker))

    result = pd.DataFrame(records)
    if result.empty:
        return result

    result = result.sort_values(["ticker", "date"]).reset_index(drop=True)
    return result


def _row_to_record(row: pd.Series, ticker: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "date": row.get("date"),
        "open": float(row.get("open", 0) or 0),
        "high": float(row.get("high", 0) or 0),
        "low": float(row.get("low", 0) or 0),
        "close": float(row.get("close", 0) or 0),
        "volume": int(row.get("volume", 0) or 0),
        "pct_change": float(row.get("pct_change", 0) or 0),
    }


def get_latest_snapshot(
    tickers: list[str],
    as_of: date | None = None,
) -> pd.DataFrame:
    """Return one row per ticker for the most recent trading session on or before *as_of*."""
    df = fetch_eod_prices(tickers, as_of=as_of, lookback_days=5)
    if df.empty:
        return df
    # Keep only rows on or before as_of
    ref = as_of or date.today()
    df = df[df["date"] <= ref]
    # Latest row per ticker
    return df.sort_values("date").groupby("ticker").last().reset_index()
