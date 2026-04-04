"""Anthropic Claude API wrapper for sentiment analysis and report generation.

Provides LLM-powered analysis capabilities. All methods gracefully handle
missing API keys by logging errors and returning None.
"""

import json
import logging

from config import get_settings

logger = logging.getLogger(__name__)


class LLMProvider:
    """Claude API wrapper for sentiment analysis and market reports."""

    def __init__(self) -> None:
        """Initialize LLMProvider with Anthropic client if API key is available."""
        self._client = None
        settings = get_settings()
        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                logger.info("Anthropic client initialized.")
            except ImportError:
                logger.warning("anthropic package not installed.")
            except Exception:
                logger.exception("Failed to initialize Anthropic client.")
        else:
            logger.warning("ANTHROPIC_API_KEY not set. LLM features disabled.")

    def analyze_sentiment(self, headlines: list[str]) -> list[dict] | None:
        """Analyze sentiment of news headlines using Claude.

        Args:
            headlines: List of news headline strings to analyze.

        Returns:
            List of dicts with 'headline', 'score' (-1.0 to 1.0), and
            'label' (Very Bearish to Very Bullish). Returns None on error.
        """
        if self._client is None:
            logger.error("Anthropic client not available for sentiment analysis.")
            return None

        if not headlines:
            return []

        prompt = f"""Analyze the sentiment of each news headline below.
For each headline, provide:
- score: a float from -1.0 (very bearish/negative) to 1.0 (very bullish/positive)
- label: one of "Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"

Headlines:
{json.dumps(headlines, ensure_ascii=False)}

Respond with a JSON array only, no extra text. Example:
[{{"headline": "...", "score": 0.5, "label": "Bullish"}}]
"""

        try:
            message = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )

            response_text = message.content[0].text.strip()
            # Extract JSON from response (handle possible markdown code blocks)
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                response_text = "\n".join(json_lines)

            results = json.loads(response_text)
            logger.info("Analyzed sentiment for %d headlines.", len(results))
            return results
        except json.JSONDecodeError:
            logger.exception("Failed to parse LLM sentiment response as JSON.")
            return None
        except Exception:
            logger.exception("Failed to analyze sentiment via Claude.")
            return None

    def generate_market_report(self, market_data: dict) -> str | None:
        """Generate a daily market report using Claude.

        Args:
            market_data: Dictionary containing market summary data including
                indices, top gainers/losers, sector performance, etc.

        Returns:
            Markdown-formatted market report string. None on error.
        """
        if self._client is None:
            logger.error("Anthropic client not available for report generation.")
            return None

        prompt = f"""You are a professional financial analyst. Based on the following market data,
generate a concise daily market report in English.

Market Data:
{json.dumps(market_data, ensure_ascii=False, default=str)}

The report should include:
1. **Market Overview**: Summary of major indices performance
2. **Sector Highlights**: Notable sector movements
3. **Key Movers**: Top gainers and losers with brief analysis
4. **Market Sentiment**: Overall market sentiment assessment
5. **Outlook**: Brief forward-looking commentary

Format the report in Markdown. Keep it concise but informative (300-500 words).
"""

        try:
            message = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )

            report = message.content[0].text.strip()
            logger.info("Generated daily market report (%d chars).", len(report))
            return report
        except Exception:
            logger.exception("Failed to generate market report via Claude.")
            return None
