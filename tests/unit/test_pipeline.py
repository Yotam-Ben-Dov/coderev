from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.github.models import PullRequest
from src.services.llm.base import CommentCategory, CommentSeverity, InlineComment, ReviewResponse
from src.services.review.pipeline import ReviewPipeline


class TestReviewPipeline:
    """Tests for the review pipeline."""

    @pytest.fixture
    def mock_github_client(self) -> MagicMock:
        client = MagicMock()
        client.get_pull_request = AsyncMock()
        client.get_pull_request_diff = AsyncMock()
        client.get_file_content = AsyncMock()
        client.create_review = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_llm_router(self) -> MagicMock:
        router = MagicMock()
        router.review_code = AsyncMock()
        return router

    @pytest.fixture
    def sample_pr(self) -> PullRequest:
        return PullRequest(
            id=1,
            number=42,
            title="Test PR",
            body="Test description",
            state="open",
            html_url="https://github.com/owner/repo/pull/42",
            diff_url="https://github.com/owner/repo/pull/42.diff",
            user={"login": "testuser", "id": 1},
            head_sha="abc123",
            base_sha="def456",
            head_ref="feature",
            base_ref="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

    @pytest.fixture
    def sample_diff(self) -> str:
        return """diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1,3 +1,5 @@
 def hello():
-    print("Hello")
+    print("Hello, World!")
+    return True
"""

    @pytest.fixture
    def sample_llm_response(self) -> ReviewResponse:
        return ReviewResponse(
            summary="Good changes!",
            verdict="approve",
            comments=[
                InlineComment(
                    path="main.py",
                    line=3,
                    body="Nice improvement!",
                    category=CommentCategory.SUGGESTION,
                    severity=CommentSeverity.INFO,
                ),
            ],
            tokens_used=500,
            model="test-model",
            cost_usd=0.005,
        )

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        mock_github_client: MagicMock,
        mock_llm_router: MagicMock,
        sample_pr: PullRequest,
        sample_diff: str,
        sample_llm_response: ReviewResponse,
    ) -> None:
        """Test successful pipeline execution."""
        mock_github_client.get_pull_request.return_value = sample_pr
        mock_github_client.get_pull_request_diff.return_value = sample_diff
        mock_github_client.get_file_content.return_value = "def hello():\n    pass"
        mock_github_client.create_review.return_value = {"id": 123}
        mock_llm_router.review_code.return_value = sample_llm_response

        pipeline = ReviewPipeline(
            github_client=mock_github_client,
            llm_router=mock_llm_router,
        )

        result = await pipeline.execute(
            owner="owner",
            repo="repo",
            pr_number=42,
            post_review=True,
        )

        assert result.pr_number == 42
        assert result.files_reviewed == 1
        assert result.total_comments == 1
        assert result.verdict == "approve"
        assert result.review_posted is True
        assert result.github_review_id == 123
        assert result.review_id is None

        mock_github_client.create_review.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_python_files(
        self,
        mock_github_client: MagicMock,
        mock_llm_router: MagicMock,
        sample_pr: PullRequest,
    ) -> None:
        """Test pipeline when no Python files are changed."""
        mock_github_client.get_pull_request.return_value = sample_pr
        mock_github_client.get_pull_request_diff.return_value = """diff --git a/style.css b/style.css
--- a/style.css
+++ b/style.css
@@ -1 +1 @@
-old
+new
"""

        pipeline = ReviewPipeline(
            github_client=mock_github_client,
            llm_router=mock_llm_router,
        )

        result = await pipeline.execute(
            owner="owner",
            repo="repo",
            pr_number=42,
            post_review=False,
        )

        assert result.files_reviewed == 0
        assert result.review_posted is False
        assert result.review_id is None
        mock_llm_router.review_code.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_without_posting(
        self,
        mock_github_client: MagicMock,
        mock_llm_router: MagicMock,
        sample_pr: PullRequest,
        sample_diff: str,
        sample_llm_response: ReviewResponse,
    ) -> None:
        """Test pipeline without posting to GitHub."""
        mock_github_client.get_pull_request.return_value = sample_pr
        mock_github_client.get_pull_request_diff.return_value = sample_diff
        mock_github_client.get_file_content.return_value = "def hello():\n    pass"
        mock_llm_router.review_code.return_value = sample_llm_response

        pipeline = ReviewPipeline(
            github_client=mock_github_client,
            llm_router=mock_llm_router,
        )

        result = await pipeline.execute(
            owner="owner",
            repo="repo",
            pr_number=42,
            post_review=False,
        )

        assert result.review_posted is False
        assert result.github_review_id is None
        assert result.review_id is None
        mock_github_client.create_review.assert_not_called()
