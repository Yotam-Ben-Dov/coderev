"""Main review pipeline orchestration."""

from dataclasses import dataclass
from typing import Literal

import structlog

from src.core.config import settings
from src.core.exceptions import ReviewError
from src.services.github.client import GitHubClient
from src.services.github.models import PullRequest
from src.services.llm.base import ReviewRequest, ReviewResponse
from src.services.llm.router import LLMRouter
from src.services.review.diff_parser import DiffParser
from src.services.review.formatter import llm_response_to_github_review

logger = structlog.get_logger()


@dataclass
class PipelineResult:
    """Result of a review pipeline execution."""

    pr_number: int
    pr_title: str
    files_reviewed: int
    total_comments: int
    verdict: Literal["approve", "request_changes", "comment"]
    summary: str
    model_used: str
    total_tokens: int
    total_cost_usd: float
    review_posted: bool
    github_review_id: int | None = None


class ReviewPipeline:
    """Orchestrates the code review process."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        llm_router: LLMRouter | None = None,
        diff_parser: DiffParser | None = None,
    ) -> None:
        self.github = github_client or GitHubClient()
        self.llm = llm_router or LLMRouter()
        self.diff_parser = diff_parser or DiffParser()

    async def execute(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        post_review: bool = True,
    ) -> PipelineResult:
        """
        Execute the full review pipeline for a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.
            post_review: Whether to post the review to GitHub.

        Returns:
            PipelineResult with review details.
        """
        logger.info(
            "Starting review pipeline",
            owner=owner,
            repo=repo,
            pr_number=pr_number,
        )

        # 1. Fetch PR details
        pr = await self.github.get_pull_request(owner, repo, pr_number)
        logger.info("Fetched PR", title=pr.title, head_sha=pr.head_sha)

        # 2. Fetch diff
        diff = await self.github.get_pull_request_diff(owner, repo, pr_number)

        # 3. Parse diff and filter Python files
        file_diffs = self.diff_parser.parse_and_filter_python(diff)

        if not file_diffs:
            logger.info("No Python files to review")
            return PipelineResult(
                pr_number=pr_number,
                pr_title=pr.title,
                files_reviewed=0,
                total_comments=0,
                verdict="approve",
                summary="No Python files to review in this PR.",
                model_used="",
                total_tokens=0,
                total_cost_usd=0.0,
                review_posted=False,
            )

        # 4. Apply limits
        if len(file_diffs) > settings.max_files_per_review:
            logger.warning(
                "Too many files, truncating",
                total_files=len(file_diffs),
                max_files=settings.max_files_per_review,
            )
            file_diffs = file_diffs[: settings.max_files_per_review]

        # 5. Review each file
        all_responses: list[ReviewResponse] = []

        for file_diff in file_diffs:
            logger.info("Reviewing file", path=file_diff.path)

            # Fetch full file content for context
            try:
                file_content = await self.github.get_file_content(
                    owner, repo, file_diff.path, pr.head_sha
                )
            except Exception as e:
                logger.warning(
                    "Could not fetch file content",
                    path=file_diff.path,
                    error=str(e),
                )
                file_content = None

            # Build review request
            request = ReviewRequest(
                diff=file_diff.to_patch_string(),
                file_path=file_diff.path,
                file_content=file_content,
                pr_title=pr.title,
                pr_description=pr.body,
            )

            # Get LLM review
            response = await self.llm.review_code(request)
            all_responses.append(response)

        # 6. Aggregate results
        aggregated = self._aggregate_responses(all_responses, pr)

        # 7. Format for GitHub
        github_review = llm_response_to_github_review(
            aggregated,
            files_reviewed=len(file_diffs),
        )

        # 8. Post review to GitHub
        review_id = None
        if post_review:
            try:
                result = await self.github.create_review(owner, repo, pr_number, github_review)
                review_id = result.get("id")
                logger.info("Posted review to GitHub", review_id=review_id)
            except Exception as e:
                logger.error("Failed to post review", error=str(e))
                raise ReviewError(f"Failed to post review: {e}") from e

        return PipelineResult(
            pr_number=pr_number,
            pr_title=pr.title,
            files_reviewed=len(file_diffs),
            total_comments=len(aggregated.comments),
            verdict=aggregated.verdict,
            summary=aggregated.summary,
            model_used=aggregated.model,
            total_tokens=aggregated.tokens_used,
            total_cost_usd=aggregated.cost_usd,
            review_posted=post_review,
            github_review_id=review_id,
        )

    def _aggregate_responses(
        self,
        responses: list[ReviewResponse],
        pr: PullRequest,
    ) -> ReviewResponse:
        """Aggregate multiple file reviews into a single response."""
        if not responses:
            return ReviewResponse(
                summary="No files reviewed.",
                verdict="comment",
                comments=[],
                tokens_used=0,
                model="",
                cost_usd=0.0,
            )

        # Collect all comments
        all_comments = []
        for response in responses:
            all_comments.extend(response.comments)

        # Aggregate tokens and cost
        total_tokens = sum(r.tokens_used for r in responses)
        total_cost = sum(r.cost_usd for r in responses)

        # Determine overall verdict (most severe wins)
        verdicts = [r.verdict for r in responses]
        if "request_changes" in verdicts:
            overall_verdict: Literal["approve", "request_changes", "comment"] = "request_changes"
        elif "comment" in verdicts:
            overall_verdict = "comment"
        else:
            overall_verdict = "approve"

        # Build combined summary
        if len(responses) == 1:
            combined_summary = responses[0].summary
        else:
            summaries = []
            for response in responses:
                if response.comments:
                    # Find the file path from comments
                    file_path = response.comments[0].path
                    summaries.append(f"**{file_path}**: {response.summary}")

            if summaries:
                combined_summary = "### File Reviews\n\n" + "\n\n".join(summaries)
            else:
                combined_summary = "All files look good!"

        # Use model from first response
        model = responses[0].model if responses else ""

        return ReviewResponse(
            summary=combined_summary,
            verdict=overall_verdict,
            comments=all_comments,
            tokens_used=total_tokens,
            model=model,
            cost_usd=total_cost,
        )

    async def close(self) -> None:
        """Clean up resources."""
        await self.github.close()
