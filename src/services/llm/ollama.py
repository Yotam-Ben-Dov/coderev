import json
import re
from typing import Any

import httpx
import structlog

from src.core.config import settings
from src.core.exceptions import LLMError, LLMProviderUnavailableError
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


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM inference."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.default_model_ollama
        self._base_url = settings.ollama_host

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/api/tags")
                is_ok: bool = response.status_code == 200
                return is_ok
        except Exception:
            return False

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Local inference is free!"""
        return 0.0

    async def review_code(self, request: ReviewRequest) -> ReviewResponse:
        """Review code using local Ollama model."""
        if not self.is_available():
            raise LLMProviderUnavailableError("Ollama server is not available")

        user_prompt = build_review_prompt(
            diff=request.diff,
            file_path=request.file_path,
            file_content=request.file_content,
            context=request.context,
            pr_title=request.pr_title,
            pr_description=request.pr_description,
        )

        # Combine system and user prompt for Ollama
        full_prompt = f"{REVIEW_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"

        logger.debug(
            "Sending review request to Ollama",
            model=self._model,
            file=request.file_path,
        )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 4096,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            logger.error("Ollama API error", error=str(e))
            raise LLMError(f"Ollama API error: {e}") from e

        response_text = data.get("response", "")

        # Ollama doesn't always provide token counts
        # Estimate based on response length
        estimated_tokens = len(full_prompt.split()) + len(response_text.split())

        parsed = self._parse_response(response_text, request.file_path)

        return ReviewResponse(
            summary=parsed["summary"],
            verdict=parsed["verdict"],
            comments=parsed["comments"],
            tokens_used=estimated_tokens,
            model=self._model,
            cost_usd=0.0,
        )

    def _parse_response(
        self,
        response_text: str,
        file_path: str,
    ) -> dict[str, Any]:
        """Parse LLM response into structured format."""
        # Try to extract JSON from the response
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object in response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else response_text.strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse Ollama response as JSON",
                response=response_text[:500],
                error=str(e),
            )
            # Return a fallback response
            return {
                "summary": "Unable to parse model response. Please review the changes manually.",
                "verdict": "comment",
                "comments": [],
            }

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
