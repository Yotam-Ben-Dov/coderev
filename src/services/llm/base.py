from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class CommentCategory(str, Enum):
    BUG = "BUG"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    STYLE = "STYLE"
    SUGGESTION = "SUGGESTION"
    DOCUMENTATION = "DOCUMENTATION"


class CommentSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class InlineComment:
    """A single inline comment on a specific line."""

    path: str
    line: int
    body: str
    category: CommentCategory = CommentCategory.SUGGESTION
    severity: CommentSeverity = CommentSeverity.INFO


@dataclass
class ReviewRequest:
    """Request for an LLM code review."""

    diff: str
    file_path: str
    file_content: str | None = None
    context: str | None = None
    pr_title: str | None = None
    pr_description: str | None = None


@dataclass
class ReviewResponse:
    """Response from an LLM code review."""

    summary: str
    verdict: Literal["approve", "request_changes", "comment"]
    comments: list[InlineComment] = field(default_factory=list)
    tokens_used: int = 0
    model: str = ""
    cost_usd: float = 0.0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier."""
        pass

    @abstractmethod
    async def review_code(self, request: ReviewRequest) -> ReviewResponse:
        """Review code and return structured feedback."""
        pass

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a given number of tokens."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""
        pass
