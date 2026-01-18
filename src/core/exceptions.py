from typing import Any


class CodeRevError(Exception):
    """Base exception for CodeRev application."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class GitHubError(CodeRevError):
    """Errors related to GitHub API interactions."""

    pass


class GitHubAuthenticationError(GitHubError):
    """GitHub authentication failed."""

    pass


class GitHubRateLimitError(GitHubError):
    """GitHub API rate limit exceeded."""

    def __init__(self, reset_at: int, message: str = "Rate limit exceeded") -> None:
        self.reset_at = reset_at
        super().__init__(message, {"reset_at": reset_at})


class GitHubNotFoundError(GitHubError):
    """Requested GitHub resource not found."""

    pass


class DiffParseError(CodeRevError):
    """Error parsing diff content."""

    pass


class LLMError(CodeRevError):
    """Errors related to LLM interactions."""

    pass


class LLMProviderUnavailableError(LLMError):
    """LLM provider is not available or configured."""

    pass


class LLMRateLimitError(LLMError):
    """LLM provider rate limit exceeded."""

    pass


class LLMResponseParseError(LLMError):
    """Failed to parse LLM response into expected format."""

    pass


class ReviewError(CodeRevError):
    """Errors during the review process."""

    pass


class ReviewTimeoutError(ReviewError):
    """Review took too long to complete."""

    pass


class ConfigurationError(CodeRevError):
    """Invalid or missing configuration."""

    pass
