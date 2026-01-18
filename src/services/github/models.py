from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FileStatus(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class User(BaseModel):
    """GitHub user information."""

    login: str
    id: int
    avatar_url: str | None = None
    html_url: str | None = None


class Repository(BaseModel):
    """GitHub repository information."""

    id: int
    name: str
    full_name: str
    owner: User
    html_url: str
    default_branch: str = "main"
    private: bool = False


class PullRequestFile(BaseModel):
    """A file changed in a pull request."""

    sha: str
    filename: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    previous_filename: str | None = None


class PullRequest(BaseModel):
    """Pull request information from GitHub."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    number: int
    title: str
    body: str | None = None
    state: Literal["open", "closed"]
    html_url: str
    diff_url: str
    user: User
    head_sha: str = Field(..., alias="head_sha")
    base_sha: str = Field(..., alias="base_sha")
    head_ref: str
    base_ref: str
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None


class ReviewComment(BaseModel):
    """A review comment to post on a PR."""

    path: str
    line: int
    body: str
    side: Literal["LEFT", "RIGHT"] = "RIGHT"


class Review(BaseModel):
    """A complete review to submit."""

    body: str
    event: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"] = "COMMENT"
    comments: list[ReviewComment] = Field(default_factory=list)


class WebhookPullRequestEvent(BaseModel):
    """Parsed webhook payload for PR events."""

    action: str
    number: int
    pull_request: dict[str, Any]
    repository: dict[str, Any]
    sender: dict[str, Any]

    @property
    def repo_full_name(self) -> str:
        return str(self.repository.get("full_name", ""))

    @property
    def pr_title(self) -> str:
        return str(self.pull_request.get("title", ""))

    @property
    def head_sha(self) -> str:
        head = self.pull_request.get("head", {})
        if isinstance(head, dict):
            return str(head.get("sha", ""))
        return ""
