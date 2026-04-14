"""Groq API client wrapper with retries, timeouts, and structured-output helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from market_agent.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stub / dry-run support
# ---------------------------------------------------------------------------

_STUB_NARRATIVE = """## Market Summary
Markets ended the session with mixed performance. Technology led gains while energy lagged.

## Focus Tickers
- **SPY**: Modest gain on above-average volume — broad market resilience.
- **QQQ**: Tech-driven outperformance; watch RSI for near-term exhaustion.
- **XLE**: Underperformer today; energy macro headwinds persist.

## Recommended Actions for Next Morning
1. Monitor SPY open relative to today's close for continuation signal.
2. Consider trimming QQQ exposure if pre-market gap exceeds 0.5 %.
3. Avoid adding to XLE until price stabilises above key support.

## Behavior Coaching Note
Stay patient — chasing overnight gaps has historically reduced returns for retail investors.
Review your checklist before executing any trade at open.

*⚠️ This report is for informational purposes only and does not constitute financial advice.*
"""


class GroqClient:
    """Thin wrapper around the official Groq SDK with retry logic."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._client: Any = None

        if not dry_run:
            if not settings.groq_api_key:
                raise ValueError(
                    "GROQ_API_KEY is not set. "
                    "Either set it in .env or pass --dry-run to skip LLM calls."
                )
            try:
                from groq import Groq  # type: ignore[import-untyped]

                self._client = Groq(
                    api_key=settings.groq_api_key,
                    timeout=settings.groq_timeout,
                    max_retries=0,  # we handle retries ourselves via tenacity
                )
            except ImportError as exc:
                raise ImportError("Install the 'groq' package: pip install groq") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Return the model's text response, or a stub when dry_run=True."""
        if self.dry_run:
            logger.info("DRY RUN — returning stub LLM response.")
            return _STUB_NARRATIVE

        return self._complete_with_retry(system_prompt, user_prompt, temperature, max_tokens)

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return a parsed JSON object from the model, or an empty dict when dry_run=True."""
        if self.dry_run:
            logger.info("DRY RUN — returning stub JSON response.")
            return {"actions": [], "coaching_note": "Stub note — dry run mode."}

        raw = self._complete_with_retry(
            system_prompt,
            user_prompt + "\n\nRespond ONLY with valid JSON — no markdown, no preamble.",
            temperature,
            max_tokens,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # strip markdown fences if the model added them
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(cleaned)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(settings.groq_max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _complete_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        try:
            response = self._client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except RetryError:
            logger.error("Groq API failed after %d retries.", settings.groq_max_retries)
            raise
        except Exception as exc:
            logger.warning("Groq API error (will retry): %s", exc)
            raise
