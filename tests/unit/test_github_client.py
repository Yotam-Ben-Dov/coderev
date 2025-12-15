from unittest.mock import AsyncMock, patch

import pytest

from src.core.exceptions import GitHubAuthenticationError, GitHubNotFoundError
from src.services.github.client import GitHubClient
from src.services.github.models import Review, ReviewComment


class TestGitHubClient:
    """Tests for the GitHub client."""

    @pytest.fixture
    def client(self) -> GitHubClient:
        return GitHubClient(token="test-token")

    @pytest.mark.asyncio
    async def test_get_pull_request(self, client: GitHubClient) -> None:
        """Test fetching a pull request."""
        mock_response = {
            "id": 12345,
            "number": 1,
            "title": "Test PR",
            "body": "Test body",
            "state": "open",
            "html_url": "https://github.com/owner/repo/pull/1",
            "diff_url": "https://github.com/owner/repo/pull/1.diff",
            "user": {
                "login": "testuser",
                "id": 1,
            },
            "head": {
                "sha": "abc123",
                "ref": "feature-branch",
            },
            "base": {
                "sha": "def456",
                "ref": "main",
            },
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "merged_at": None,
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            pr = await client.get_pull_request("owner", "repo", 1)

        assert pr.number == 1
        assert pr.title == "Test PR"
        assert pr.head_sha == "abc123"
        assert pr.head_ref == "feature-branch"

    @pytest.mark.asyncio
    async def test_get_pull_request_not_found(self, client: GitHubClient) -> None:
        """Test handling of non-existent PR."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubNotFoundError("Not found")

            with pytest.raises(GitHubNotFoundError):
                await client.get_pull_request("owner", "repo", 999)

    @pytest.mark.asyncio
    async def test_get_pull_request_files(self, client: GitHubClient) -> None:
        """Test fetching PR files."""
        mock_response = [
            {
                "sha": "abc123",
                "filename": "src/main.py",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "changes": 15,
                "patch": "@@ -1,3 +1,4 @@\n old\n+new",
            },
            {
                "sha": "def456",
                "filename": "tests/test_main.py",
                "status": "added",
                "additions": 20,
                "deletions": 0,
                "changes": 20,
                "patch": "@@ -0,0 +1,20 @@\n+new test",
            },
        ]

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            files = await client.get_pull_request_files("owner", "repo", 1)

        assert len(files) == 2
        assert files[0].filename == "src/main.py"
        assert files[0].status.value == "modified"
        assert files[1].status.value == "added"

    @pytest.mark.asyncio
    async def test_create_review(self, client: GitHubClient) -> None:
        """Test submitting a review."""
        review = Review(
            body="Overall looks good!",
            event="COMMENT",
            comments=[
                ReviewComment(
                    path="src/main.py",
                    line=10,
                    body="Consider adding a docstring here.",
                )
            ],
        )

        mock_response = {"id": 1, "state": "COMMENTED"}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.create_review("owner", "repo", 1, review)

        assert result["id"] == 1  # <-- ADD THIS LINE
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        assert call_kwargs[1]["json"]["body"] == "Overall looks good!"
        assert len(call_kwargs[1]["json"]["comments"]) == 1

    @pytest.mark.asyncio
    async def test_authentication_error(self, client: GitHubClient) -> None:
        """Test handling of authentication errors."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubAuthenticationError("Invalid token")

            with pytest.raises(GitHubAuthenticationError):
                await client.get_pull_request("owner", "repo", 1)
