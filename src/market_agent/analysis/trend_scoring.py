"""Deterministic trend-scoring for the watchlist.

Scoring formula (all components normalised to [0, 1] within the batch):

    score = 0.50 * |pct_change|          # magnitude of daily move
          + 0.30 * volume_anomaly        # today's volume vs. 5-day avg
          + 0.20 * volatility_proxy      # (high - low) / close

Focus tickers are those with the highest composite score.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Scoring weights (must sum to 1.0)
_W_MOVE = 0.50
_W_VOL_ANOMALY = 0.30
_W_VOLATILITY = 0.20


@dataclass
class TickerScore:
    ticker: str
    pct_change: float
    volume: int
    volume_anomaly: float  # today vol / avg vol (>1 means above-average)
    volatility_proxy: float  # (high-low)/close
    composite_score: float
    direction: str = field(init=False)

    def __post_init__(self) -> None:
        self.direction = "up" if self.pct_change >= 0 else "down"


def score_tickers(
    snapshot: pd.DataFrame,
    top_n: int = 3,
    history: pd.DataFrame | None = None,
) -> tuple[list[TickerScore], list[TickerScore]]:
    """Score and rank tickers.

    Args:
        snapshot: One row per ticker for the reference trading session.
            Required columns: ticker, close, pct_change, volume, high, low.
        top_n: Number of focus tickers to return.
        history: Optional multi-day DataFrame (same schema as snapshot) used
            to compute volume anomalies.  If omitted, volume anomaly = 1.0.

    Returns:
        (all_scores, focus_tickers) where focus_tickers are the top_n by
        composite score.
    """
    if snapshot.empty:
        return [], []

    rows = snapshot.copy()

    # ── Volume anomaly ────────────────────────────────────────────────────────
    if history is not None and not history.empty:
        avg_vol = (
            history.groupby("ticker")["volume"]
            .mean()
            .rename("avg_volume")
            .reset_index()
        )
        rows = rows.merge(avg_vol, on="ticker", how="left")
        rows["avg_volume"] = rows["avg_volume"].fillna(rows["volume"])
        rows["volume_anomaly"] = rows["volume"] / rows["avg_volume"].replace(0, np.nan)
        rows["volume_anomaly"] = rows["volume_anomaly"].fillna(1.0)
    else:
        rows["volume_anomaly"] = 1.0

    # ── Volatility proxy ─────────────────────────────────────────────────────
    rows["volatility_proxy"] = (rows["high"] - rows["low"]) / rows["close"].replace(0, np.nan)
    rows["volatility_proxy"] = rows["volatility_proxy"].fillna(0.0)

    # ── Normalise each component to [0, 1] ───────────────────────────────────
    def _minmax(series: pd.Series) -> pd.Series:
        lo, hi = series.min(), series.max()
        if hi == lo:
            return pd.Series(np.zeros(len(series)), index=series.index)
        return (series - lo) / (hi - lo)

    norm_move = _minmax(rows["pct_change"].abs())
    norm_vol_anomaly = _minmax(rows["volume_anomaly"])
    norm_volatility = _minmax(rows["volatility_proxy"])

    rows["composite_score"] = (
        _W_MOVE * norm_move
        + _W_VOL_ANOMALY * norm_vol_anomaly
        + _W_VOLATILITY * norm_volatility
    )

    rows = rows.sort_values("composite_score", ascending=False).reset_index(drop=True)

    all_scores = [
        TickerScore(
            ticker=row["ticker"],
            pct_change=float(row["pct_change"]),
            volume=int(row["volume"]),
            volume_anomaly=float(row["volume_anomaly"]),
            volatility_proxy=float(row["volatility_proxy"]),
            composite_score=float(row["composite_score"]),
        )
        for _, row in rows.iterrows()
    ]

    focus = all_scores[:top_n]
    logger.info(
        "Focus tickers: %s",
        [(s.ticker, round(s.composite_score, 3)) for s in focus],
    )
    return all_scores, focus
