import json
import re
from typing import Any

import structlog

from src.core.config import settings
from src.core.exceptions import LLMError, LLMProviderUnavailableError, LLMResponseParseError
from src.prompts.review import REVIEW_SYSTEM_PROMPT, build_review_prompt
from src.services.llm.base import (
    CommentCategory,
    CommentSeverity,
    InlineComment,
    LLMProvider,
    ReviewRequest,
    ReviewResponse,
)

logger = structlog.get_logger()

# Pricing per 1M tokens (as of 2024)
ANTHROPIC_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider for code review."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.default_model_anthropic
        self._client: Any = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self) -> Any:
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            if not self.is_available():
                raise LLMProviderUnavailableError("Anthropic API key not configured")

            import anthropic

            self._client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key.get_secret_value()  # type: ignore[union-attr]
            )
        return self._client

    def is_available(self) -> bool:
        return settings.anthropic_api_key is not None

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = ANTHROPIC_PRICING.get(
            self._model,
            {"input": 3.00, "output": 15.00},  # Default to Sonnet pricing
        )
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    async def review_code(self, request: ReviewRequest) -> ReviewResponse:
        """Review code using Claude."""
        client = self._get_client()

        user_prompt = build_review_prompt(
            diff=request.diff,
            file_path=request.file_path,
            file_content=request.file_content,
            context=request.context,
            pr_title=request.pr_title,
            pr_description=request.pr_description,
        )

        logger.debug(
            "Sending review request to Anthropic",
            model=self._model,
            file=request.file_path,
        )

        try:
            # Note: Using sync client in async context for simplicity
            # For production, consider using anthropic's async client
            message = client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=REVIEW_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:
            logger.error("Anthropic API error", error=str(e))
            raise LLMError(f"Anthropic API error: {e}") from e

        # Extract response text
        response_text = message.content[0].text

        # Parse tokens
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        # Parse the JSON response
        parsed = self._parse_response(response_text, request.file_path)

        return ReviewResponse(
            summary=parsed["summary"],
            verdict=parsed["verdict"],
            comments=parsed["comments"],
            tokens_used=input_tokens + output_tokens,
            model=self._model,
            cost_usd=self.estimate_cost(input_tokens, output_tokens),
        )

    def _parse_response(
        self,
        response_text: str,
        file_path: str,
    ) -> dict[str, Any]:
        """Parse LLM response into structured format."""
        # Try to extract JSON from the response
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        json_str = json_match.group(1) if json_match else response_text.strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse LLM response as JSON",
                response=response_text[:500],
                error=str(e),
            )
            raise LLMResponseParseError(f"Invalid JSON in response: {e}") from e

        # Validate and transform
        comments = []
        for c in data.get("comments", []):
            try:
                comments.append(
                    InlineComment(
                        path=file_path,
                        line=int(c["line"]),
                        body=c["body"],
                        category=CommentCategory(c.get("category", "SUGGESTION").upper()),
                        severity=CommentSeverity(c.get("severity", "INFO").upper()),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed comment", comment=c, error=str(e))
                continue

        verdict = data.get("verdict", "comment").lower()
        if verdict not in ("approve", "request_changes", "comment"):
            verdict = "comment"

        return {
            "summary": data.get("summary", "No summary provided."),
            "verdict": verdict,
            "comments": comments,
        }
