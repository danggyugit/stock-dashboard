"""Anthropic Claude API wrapper for sentiment analysis and reports."""

import json
import logging

import streamlit as st

logger = logging.getLogger(__name__)


def _get_anthropic_key() -> str:
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


class LLMProvider:
    """Claude API wrapper for sentiment analysis and market reports."""

    def __init__(self) -> None:
        self._client = None
        key = _get_anthropic_key()
        if key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=key)
            except Exception:
                logger.warning("Anthropic client init failed.")

    def analyze_sentiment(self, headlines: list[str]) -> list[dict] | None:
        """Analyze sentiment of news headlines using Claude."""
        if self._client is None or not headlines:
            return None

        prompt = f"""Analyze the sentiment of each news headline below.
For each headline, provide:
- score: a float from -1.0 (very bearish) to 1.0 (very bullish)
- label: one of "Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"

Headlines:
{json.dumps(headlines, ensure_ascii=False)}

Respond with a JSON array only:
[{{"headline": "...", "score": 0.5, "label": "Bullish"}}]
"""
        try:
            msg = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                text = "\n".join(json_lines)
            return json.loads(text)
        except Exception:
            logger.exception("Sentiment analysis failed.")
            return None

    def generate_market_report(self, market_data: dict) -> str | None:
        """Generate a daily market report using Claude."""
        if self._client is None:
            return None

        prompt = f"""You are a professional financial analyst. Based on the following market data,
generate a concise daily market report in English.

Market Data:
{json.dumps(market_data, ensure_ascii=False, default=str)}

Include: Market Overview, Sector Highlights, Key Movers, Market Sentiment, Outlook.
Format in Markdown. 300-500 words.
"""
        try:
            msg = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception:
            logger.exception("Report generation failed.")
            return None
