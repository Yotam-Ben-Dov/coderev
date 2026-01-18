"""GitHub API client with metrics instrumentation."""

import time
from typing import Any

import httpx
import structlog

from src.core.config import settings
from src.core.exceptions import (
    GitHubAuthenticationError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from src.core.metrics import record_github_api_call
from src.services.github.models import (
    FileStatus,
    PullRequest,
    PullRequestFile,
    Review,
)

logger = structlog.get_logger()


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.github_token.get_secret_value()
        self.base_url = settings.github_api_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _extract_endpoint_name(self, endpoint: str) -> str:
        """
        Extract a normalized endpoint name for metrics.

        Converts:
            /repos/owner/repo/pulls/123 -> pulls
            /repos/owner/repo/pulls/123/files -> pulls_files
            /repos/owner/repo/pulls/123/reviews -> pulls_reviews
        """
        parts = endpoint.strip("/").split("/")

        # Skip 'repos', owner, repo parts
        if len(parts) >= 3 and parts[0] == "repos":
            parts = parts[3:]  # Remove repos/owner/repo

        # Filter out numeric parts (IDs)
        parts = [p for p in parts if not p.isdigit()]

        # Join remaining parts with underscore
        return "_".join(parts) if parts else "unknown"

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any] | str:
        """Make an authenticated request to GitHub API."""
        client = await self._get_client()
        endpoint_name = self._extract_endpoint_name(endpoint)

        logger.debug("GitHub API request", method=method, endpoint=endpoint)

        start_time = time.perf_counter()
        status_code = 0
        rate_limit_remaining = None
        rate_limit_reset = None

        try:
            response = await client.request(method, endpoint, **kwargs)
            status_code = response.status_code

            # Extract rate limit headers
            rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
            rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))

            if response.status_code == 401:
                raise GitHubAuthenticationError("Invalid GitHub token")

            if response.status_code == 403:
                if "rate limit" in response.text.lower():
                    reset_at = int(response.headers.get("X-RateLimit-Reset", 0))
                    raise GitHubRateLimitError(reset_at=reset_at)
                raise GitHubAuthenticationError("Access forbidden")

            if response.status_code == 404:
                raise GitHubNotFoundError(f"Resource not found: {endpoint}")

            if response.status_code >= 400:
                raise GitHubError(
                    f"GitHub API error: {response.status_code}",
                    details={"response": response.text},
                )

            # Handle diff responses (plain text)
            headers = kwargs.get("headers", {})
            if isinstance(headers, dict) and "application/vnd.github.v3.diff" in headers.get(
                "Accept", ""
            ):
                return response.text

            result: dict[str, Any] | list[Any] = response.json()
            return result

        finally:
            # Always record metrics
            duration_seconds = time.perf_counter() - start_time
            record_github_api_call(
                endpoint=endpoint_name,
                method=method,
                status_code=status_code,
                duration_seconds=duration_seconds,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
            )

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """Fetch pull request details."""
        data = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")

        if not isinstance(data, dict):
            raise GitHubError("Unexpected response format")

        return PullRequest(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            html_url=data["html_url"],
            diff_url=data["diff_url"],
            user=data["user"],
            head_sha=data["head"]["sha"],
            base_sha=data["base"]["sha"],
            head_ref=data["head"]["ref"],
            base_ref=data["base"]["ref"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            merged_at=data.get("merged_at"),
        )

    async def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[PullRequestFile]:
        """Fetch the list of files changed in a PR."""
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
            params={"per_page": 100},
        )

        if not isinstance(data, list):
            raise GitHubError("Unexpected response format")

        files = []
        for file_data in data:
            files.append(
                PullRequestFile(
                    sha=file_data["sha"],
                    filename=file_data["filename"],
                    status=FileStatus(file_data["status"]),
                    additions=file_data.get("additions", 0),
                    deletions=file_data.get("deletions", 0),
                    changes=file_data.get("changes", 0),
                    patch=file_data.get("patch"),
                    previous_filename=file_data.get("previous_filename"),
                )
            )

        return files

    async def get_pull_request_diff(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> str:
        """Fetch the raw diff for a PR."""
        diff = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )

        if not isinstance(diff, str):
            raise GitHubError("Unexpected response format for diff")

        return diff

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> str:
        """Fetch the content of a file at a specific ref."""
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers={"Accept": "application/vnd.github.v3.raw"},
        )

        if isinstance(data, str):
            return data

        raise GitHubError("Unexpected response format for file content")

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        review: Review,
    ) -> dict[str, Any]:
        """Submit a review on a pull request."""
        payload: dict[str, Any] = {
            "body": review.body,
            "event": review.event,
        }

        if review.comments:
            payload["comments"] = [
                {
                    "path": c.path,
                    "line": c.line,
                    "body": c.body,
                    "side": c.side,
                }
                for c in review.comments
            ]

        data = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json=payload,
        )

        if not isinstance(data, dict):
            raise GitHubError("Unexpected response format")

        logger.info(
            "Review submitted",
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            comment_count=len(review.comments),
        )

        return data

    async def create_issue_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> dict[str, Any]:
        """Create a simple comment on a PR (not a review)."""
        data = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )

        if not isinstance(data, dict):
            raise GitHubError("Unexpected response format")

        return data
