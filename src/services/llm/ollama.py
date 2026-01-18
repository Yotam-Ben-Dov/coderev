"""Ollama provider for local LLM inference."""

import json
import re
import time
from typing import Any

import httpx
import structlog

from src.core.config import settings
from src.core.exceptions import LLMError, LLMProviderUnavailableError
from src.core.metrics import record_llm_request
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

        start_time = time.perf_counter()
        status = "success"
        tokens_input = 0
        tokens_output = 0

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

            response_text = data.get("response", "")

            # Ollama provides token counts in some versions
            tokens_input = data.get("prompt_eval_count", 0)
            tokens_output = data.get("eval_count", 0)

            # Fallback: estimate based on response length if not provided
            if tokens_input == 0:
                tokens_input = len(full_prompt.split())
            if tokens_output == 0:
                tokens_output = len(response_text.split())

            estimated_tokens = tokens_input + tokens_output

            # Calculate timing
            duration_seconds = time.perf_counter() - start_time
            latency_ms = int(duration_seconds * 1000)

            parsed = self._parse_response(response_text, request.file_path)

            logger.info(
                "Received review response from Ollama",
                model=self._model,
                file=request.file_path,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                latency_ms=latency_ms,
                verdict=parsed["verdict"],
                comments_count=len(parsed["comments"]),
            )

            return ReviewResponse(
                summary=parsed["summary"],
                verdict=parsed["verdict"],
                comments=parsed["comments"],
                tokens_used=estimated_tokens,
                model=self._model,
                cost_usd=0.0,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                latency_ms=latency_ms,
            )

        except httpx.HTTPError as e:
            status = "error"
            logger.error("Ollama API error", error=str(e))
            raise LLMError(f"Ollama API error: {e}") from e
        except Exception as e:
            status = "error"
            logger.error("Ollama error", error=str(e))
            raise
        finally:
            # Always record metrics
            duration_seconds = time.perf_counter() - start_time
            record_llm_request(
                provider=self.name,
                model=self._model,
                status=status,
                duration_seconds=duration_seconds,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
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
