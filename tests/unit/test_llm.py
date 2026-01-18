from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.llm.anthropic import AnthropicProvider
from src.services.llm.base import (
    CommentCategory,
    CommentSeverity,
    ReviewRequest,
)
from src.services.llm.ollama import OllamaProvider
from src.services.llm.router import LLMRouter


class TestAnthropicProvider:
    """Tests for Anthropic provider."""

    @pytest.fixture
    def provider(self) -> AnthropicProvider:
        return AnthropicProvider(model="claude-sonnet-4-20250514")

    def test_parse_valid_response(self, provider: AnthropicProvider) -> None:
        """Test parsing a valid JSON response."""
        response_text = """```json
{
    "summary": "Good changes overall. Minor suggestions included.",
    "verdict": "approve",
    "comments": [
        {
            "line": 10,
            "body": "Consider adding a docstring here.",
            "category": "DOCUMENTATION",
            "severity": "INFO"
        },
        {
            "line": 25,
            "body": "This could raise a KeyError if the key doesn't exist.",
            "category": "BUG",
            "severity": "WARNING"
        }
    ]
}
```"""
        result = provider._parse_response(response_text, "src/main.py")

        assert result["summary"] == "Good changes overall. Minor suggestions included."
        assert result["verdict"] == "approve"
        assert len(result["comments"]) == 2

        assert result["comments"][0].path == "src/main.py"
        assert result["comments"][0].line == 10
        assert result["comments"][0].category == CommentCategory.DOCUMENTATION
        assert result["comments"][1].severity == CommentSeverity.WARNING

    def test_parse_response_without_code_block(self, provider: AnthropicProvider) -> None:
        """Test parsing JSON without markdown code block."""
        response_text = """{
    "summary": "Looks good!",
    "verdict": "approve",
    "comments": []
}"""
        result = provider._parse_response(response_text, "test.py")

        assert result["summary"] == "Looks good!"
        assert result["verdict"] == "approve"
        assert len(result["comments"]) == 0

    def test_parse_response_invalid_verdict_defaults_to_comment(
        self, provider: AnthropicProvider
    ) -> None:
        """Test that invalid verdict defaults to 'comment'."""
        response_text = """{
    "summary": "Test",
    "verdict": "invalid_verdict",
    "comments": []
}"""
        result = provider._parse_response(response_text, "test.py")
        assert result["verdict"] == "comment"

    def test_parse_response_malformed_comment_skipped(self, provider: AnthropicProvider) -> None:
        """Test that malformed comments are skipped."""
        response_text = """{
    "summary": "Test",
    "verdict": "comment",
    "comments": [
        {"line": 10, "body": "Valid comment", "category": "BUG", "severity": "WARNING"},
        {"body": "Missing line number"},
        {"line": "not_a_number", "body": "Invalid line"},
        {"line": 20, "body": "Another valid comment"}
    ]
}"""
        result = provider._parse_response(response_text, "test.py")

        # Only valid comments should be included
        assert len(result["comments"]) == 2
        assert result["comments"][0].line == 10
        assert result["comments"][1].line == 20

    def test_estimate_cost(self, provider: AnthropicProvider) -> None:
        """Test cost estimation."""
        cost = provider.estimate_cost(1000, 500)
        assert abs(cost - 0.0105) < 0.0001


class TestLLMRouter:
    """Tests for LLM router."""

    @pytest.fixture
    def router(self) -> LLMRouter:
        return LLMRouter(default_provider="anthropic", fallback_enabled=True)

    @pytest.mark.asyncio
    async def test_routes_to_default_provider(self, router: LLMRouter) -> None:
        """Test routing to default provider."""
        mock_response = MagicMock()
        mock_response.summary = "Test summary"
        mock_response.verdict = "approve"
        mock_response.comments = []

        with (
            patch.object(AnthropicProvider, "is_available", return_value=True),
            patch.object(
                AnthropicProvider, "review_code", new_callable=AsyncMock, return_value=mock_response
            ),
        ):
            request = ReviewRequest(
                diff="+ new line",
                file_path="test.py",
            )
            result = await router.review_code(request)

            assert result.summary == "Test summary"

    def test_get_available_providers(self, router: LLMRouter) -> None:
        """Test getting available providers."""
        with (
            patch.object(AnthropicProvider, "is_available", return_value=True),
            patch.object(OllamaProvider, "is_available", return_value=False),
        ):
            available = router.get_available_providers()

            assert "anthropic" in available
            assert "ollama" not in available
