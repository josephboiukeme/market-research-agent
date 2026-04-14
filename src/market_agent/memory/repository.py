"""Repository layer — CRUD helpers for the memory models."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from market_agent.analysis.trend_scoring import TickerScore
from market_agent.memory.models import BehaviorTag, FeedbackEntry, Recommendation, Run

logger = logging.getLogger(__name__)

_FOMO_KEYWORDS = {"buy", "bought", "chased", "fomo", "panic", "sold", "dumped"}


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, run_id: str, run_date: str) -> Run:
        run = Run(id=run_id, run_date=run_date, status="pending")
        self.session.add(run)
        self.session.commit()
        return run

    def mark_success(self, run: Run, report_md: str) -> None:
        run.status = "success"
        run.report_md = report_md
        run.updated_at = datetime.now(UTC)
        self.session.commit()

    def mark_failed(self, run: Run, error: str) -> None:
        run.status = "failed"
        run.error_message = error
        run.updated_at = datetime.now(UTC)
        self.session.commit()

    def get_latest(self) -> Run | None:
        return (
            self.session.query(Run)
            .order_by(Run.created_at.desc())
            .first()
        )

    def get_by_id(self, run_id: str) -> Run | None:
        return self.session.get(Run, run_id)


class RecommendationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_focus_tickers(
        self,
        run_id: str,
        focus: list[TickerScore],
    ) -> list[Recommendation]:
        recs = [
            Recommendation(
                run_id=run_id,
                ticker=s.ticker,
                pct_change=s.pct_change,
                volume=s.volume,
                volume_anomaly=s.volume_anomaly,
                composite_score=s.composite_score,
            )
            for s in focus
        ]
        self.session.add_all(recs)
        self.session.commit()
        return recs


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        run_id: str,
        action_taken: str | None = None,
        ticker: str | None = None,
        rating: int | None = None,
        notes: str | None = None,
    ) -> FeedbackEntry:
        entry = FeedbackEntry(
            run_id=run_id,
            ticker=ticker,
            action_taken=action_taken,
            rating=rating,
            notes=notes,
        )
        self.session.add(entry)
        self.session.commit()
        self._update_behavior_tags(action_taken, notes)
        return entry

    def _update_behavior_tags(self, action_taken: str | None, notes: str | None) -> None:
        """Derive and persist simple behavior tags from free-text fields."""
        text = " ".join(filter(None, [action_taken, notes])).lower()
        detected: set[str] = set()

        if any(kw in text for kw in _FOMO_KEYWORDS):
            detected.add("potential_fomo")
        if "hold" in text or "wait" in text or "patient" in text:
            detected.add("disciplined_holding")
        if "loss" in text or "stop" in text:
            detected.add("loss_awareness")

        for tag_name in detected:
            existing = (
                self.session.query(BehaviorTag).filter(BehaviorTag.tag == tag_name).first()
            )
            if existing:
                existing.count += 1
                existing.last_seen = datetime.now(UTC)
            else:
                self.session.add(BehaviorTag(tag=tag_name))
        self.session.commit()
