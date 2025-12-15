from src.services.llm.base import (
    CommentCategory,
    CommentSeverity,
    InlineComment,
    ReviewResponse,
)
from src.services.review.formatter import (
    format_comment_body,
    format_summary,
    llm_response_to_github_review,
)


class TestFormatter:
    """Tests for review formatter."""

    def test_format_comment_body_bug_critical(self) -> None:
        """Test formatting a critical bug comment."""
        comment = InlineComment(
            path="test.py",
            line=10,
            body="This will cause a null pointer exception.",
            category=CommentCategory.BUG,
            severity=CommentSeverity.CRITICAL,
        )
        result = format_comment_body(comment)

        assert "🔴" in result
        assert "Bug" in result
        assert "null pointer exception" in result

    def test_format_comment_body_suggestion_info(self) -> None:
        """Test formatting an info suggestion."""
        comment = InlineComment(
            path="test.py",
            line=20,
            body="Consider using a list comprehension here.",
            category=CommentCategory.SUGGESTION,
            severity=CommentSeverity.INFO,
        )
        result = format_comment_body(comment)

        assert "🔵" in result
        assert "Suggestion" in result

    def test_format_summary(self) -> None:
        """Test formatting review summary."""
        response = ReviewResponse(
            summary="Good code overall!",
            verdict="approve",
            comments=[],
            tokens_used=500,
            model="claude-sonnet-4-20250514",
            cost_usd=0.005,
        )
        result = format_summary(response, files_reviewed=3)

        assert "✅" in result
        assert "Approved" in result
        assert "Good code overall!" in result
        assert "3 file(s) reviewed" in result
        assert "claude-sonnet-4-20250514" in result

    def test_llm_response_to_github_review_approve(self) -> None:
        """Test converting approve verdict."""
        response = ReviewResponse(
            summary="LGTM!",
            verdict="approve",
            comments=[],
            tokens_used=100,
            model="test-model",
            cost_usd=0.001,
        )
        result = llm_response_to_github_review(response, files_reviewed=1)

        assert result.event == "APPROVE"
        assert "LGTM!" in result.body
        assert len(result.comments) == 0

    def test_llm_response_to_github_review_request_changes(self) -> None:
        """Test converting request_changes verdict."""
        response = ReviewResponse(
            summary="Needs fixes.",
            verdict="request_changes",
            comments=[
                InlineComment(
                    path="main.py",
                    line=15,
                    body="Fix this bug.",
                    category=CommentCategory.BUG,
                    severity=CommentSeverity.CRITICAL,
                ),
            ],
            tokens_used=200,
            model="test-model",
            cost_usd=0.002,
        )
        result = llm_response_to_github_review(response, files_reviewed=1)

        assert result.event == "REQUEST_CHANGES"
        assert len(result.comments) == 1
        assert result.comments[0].path == "main.py"
        assert result.comments[0].line == 15
        assert "Bug" in result.comments[0].body
