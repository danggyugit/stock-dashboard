"""Anthropic Claude API wrapper for sentiment analysis and reports."""

import json
import logging

import streamlit as st

logger = logging.getLogger(__name__)


def _classify_anthropic_error(exc: Exception) -> str:
    """Anthropic 예외를 사용자 친화적 메시지로 변환."""
    msg = str(exc).lower()
    if any(k in msg for k in ("529", "overloaded", "rate_limit", "429")):
        return "⏳ Claude API 한도 초과 — 잠시 후 다시 시도하세요."
    if any(k in msg for k in ("401", "403", "authentication", "api key", "invalid")):
        return "🔑 Claude API 키 오류 — secrets.toml의 ANTHROPIC_API_KEY를 확인하세요."
    if any(k in msg for k in ("timeout", "connection", "network", "ssl")):
        return "🌐 네트워크 오류 — 잠시 후 다시 시도하세요."
    if any(k in msg for k in ("500", "503", "server")):
        return "🔧 Claude 서버 일시 장애 — 잠시 후 다시 시도하세요."
    return f"❌ Claude API 오류 — {str(exc)[:100]}"


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
        except Exception as e:
            logger.warning("Sentiment analysis failed: %s", _classify_anthropic_error(e))
            return None

    def complete(self, prompt: str, max_tokens: int = 1024) -> str | None:
        """General-purpose text completion via Claude."""
        if self._client is None:
            return None
        try:
            msg = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            logger.warning("LLM completion failed: %s", _classify_anthropic_error(e))
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
        except Exception as e:
            logger.warning("Report generation failed: %s", _classify_anthropic_error(e))
            return None
