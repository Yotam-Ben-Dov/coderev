"""Main review pipeline orchestration."""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import ReviewError
from src.db.models import ReviewStatus
from src.db.repositories import RepositoryRepository, ReviewCommentRepository, ReviewRepository
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

    review_id: int | None  # Database ID
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
    latency_ms: int | None = None


class ReviewPipeline:
    """Orchestrates the code review process."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        github_client: GitHubClient | None = None,
        llm_router: LLMRouter | None = None,
        diff_parser: DiffParser | None = None,
    ) -> None:
        self.session = session
        self.github = github_client or GitHubClient()
        self.llm = llm_router or LLMRouter()
        self.diff_parser = diff_parser or DiffParser()
        
        # Repositories (initialized lazily when session is available)
        self._repo_repository: RepositoryRepository | None = None
        self._review_repository: ReviewRepository | None = None
        self._comment_repository: ReviewCommentRepository | None = None

    def _get_repositories(self) -> tuple[RepositoryRepository, ReviewRepository, ReviewCommentRepository]:
        """Get or create repository instances."""
        if self.session is None:
            raise ReviewError("Database session not available")
        
        if self._repo_repository is None:
            self._repo_repository = RepositoryRepository(self.session)
        if self._review_repository is None:
            self._review_repository = ReviewRepository(self.session)
        if self._comment_repository is None:
            self._comment_repository = ReviewCommentRepository(self.session)
        
        return self._repo_repository, self._review_repository, self._comment_repository

    async def execute(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        post_review: bool = True,
        skip_if_reviewed: bool = True,
    ) -> PipelineResult:
        """
        Execute the full review pipeline for a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.
            post_review: Whether to post the review to GitHub.
            skip_if_reviewed: Skip if this SHA was already reviewed.

        Returns:
            PipelineResult with review details.
        """
        start_time = time.time()
        review_db_id: int | None = None
        
        logger.info(
            "Starting review pipeline",
            owner=owner,
            repo=repo,
            pr_number=pr_number,
        )

        # 1. Fetch PR details
        pr = await self.github.get_pull_request(owner, repo, pr_number)
        logger.info("Fetched PR", title=pr.title, head_sha=pr.head_sha)

        # 2. Database operations (if session available)
        if self.session is not None:
            repo_repo, review_repo, comment_repo = self._get_repositories()
            
            # Get or create repository record
            db_repository, _ = await repo_repo.get_or_create(owner, repo)
            
            # Check if already reviewed (skip duplicate reviews)
            if skip_if_reviewed:
                existing = await review_repo.get_by_sha(db_repository.id, pr.head_sha)
                if existing and existing.status == ReviewStatus.COMPLETED.value:
                    logger.info(
                        "PR already reviewed at this SHA",
                        pr_number=pr_number,
                        head_sha=pr.head_sha,
                        existing_review_id=existing.id,
                    )
                    return PipelineResult(
                        review_id=existing.id,
                        pr_number=pr_number,
                        pr_title=pr.title,
                        files_reviewed=existing.files_reviewed,
                        total_comments=existing.total_comments,
                        verdict=existing.verdict or "comment",  # type: ignore
                        summary=existing.summary or "Previously reviewed.",
                        model_used=existing.model_used or "",
                        total_tokens=existing.tokens_total,
                        total_cost_usd=existing.cost_usd,
                        review_posted=existing.github_review_id is not None,
                        github_review_id=existing.github_review_id,
                        latency_ms=existing.latency_ms,
                    )
            
            # Create review record
            review_record = await review_repo.create(
                repository_id=db_repository.id,
                pr_number=pr_number,
                pr_title=pr.title,
                pr_url=pr.html_url,
                head_sha=pr.head_sha,
                base_sha=pr.base_sha,
                status=ReviewStatus.IN_PROGRESS.value,
            )
            review_db_id = review_record.id
            logger.info("Created review record", review_id=review_db_id)

        try:
            # 3. Fetch diff
            diff = await self.github.get_pull_request_diff(owner, repo, pr_number)

            # 4. Parse diff and filter Python files
            file_diffs = self.diff_parser.parse_and_filter_python(diff)

            if not file_diffs:
                logger.info("No Python files to review")
                result = PipelineResult(
                    review_id=review_db_id,
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
                
                # Update database record
                if self.session is not None and review_db_id:
                    await review_repo.mark_completed(
                        review_db_id,
                        verdict="approve",
                        summary="No Python files to review in this PR.",
                        files_reviewed=0,
                        total_comments=0,
                        model_used="",
                        tokens_input=0,
                        tokens_output=0,
                        cost_usd=0.0,
                        latency_ms=int((time.time() - start_time) * 1000),
                    )
                
                return result

            # 5. Apply limits
            if len(file_diffs) > settings.max_files_per_review:
                logger.warning(
                    "Too many files, truncating",
                    total_files=len(file_diffs),
                    max_files=settings.max_files_per_review,
                )
                file_diffs = file_diffs[: settings.max_files_per_review]

            # 6. Review each file
            all_responses: list[ReviewResponse] = []
            tokens_input = 0
            tokens_output = 0

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
                
                # Track token usage (estimate split if not provided separately)
                tokens_input += response.tokens_used // 2  # Rough estimate
                tokens_output += response.tokens_used // 2

            # 7. Aggregate results
            aggregated = self._aggregate_responses(all_responses, pr)
            
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # 8. Format for GitHub
            github_review = llm_response_to_github_review(
                aggregated,
                files_reviewed=len(file_diffs),
            )

            # 9. Post review to GitHub
            github_review_id = None
            if post_review:
                try:
                    result = await self.github.create_review(owner, repo, pr_number, github_review)
                    github_review_id = result.get("id")
                    logger.info("Posted review to GitHub", review_id=github_review_id)
                except Exception as e:
                    logger.error("Failed to post review", error=str(e))
                    raise ReviewError(f"Failed to post review: {e}") from e

            # 10. Save to database
            if self.session is not None and review_db_id:
                _, review_repo, comment_repo = self._get_repositories()
                
                # Update review record
                await review_repo.mark_completed(
                    review_db_id,
                    verdict=aggregated.verdict,
                    summary=aggregated.summary,
                    files_reviewed=len(file_diffs),
                    total_comments=len(aggregated.comments),
                    model_used=aggregated.model,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=aggregated.cost_usd,
                    latency_ms=latency_ms,
                    github_review_id=github_review_id,
                )
                
                # Save comments
                if aggregated.comments:
                    comments_data = [
                        {
                            "file_path": c.path,
                            "line_number": c.line,
                            "body": c.body,
                            "category": c.category.value.lower(),
                            "severity": c.severity.value.lower(),
                        }
                        for c in aggregated.comments
                    ]
                    await comment_repo.create_many(review_db_id, comments_data)
                
                logger.info(
                    "Saved review to database",
                    review_id=review_db_id,
                    comments_saved=len(aggregated.comments),
                )

            return PipelineResult(
                review_id=review_db_id,
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
                github_review_id=github_review_id,
                latency_ms=latency_ms,
            )

        except Exception as e:
            # Mark review as failed in database
            if self.session is not None and review_db_id:
                _, review_repo, _ = self._get_repositories()
                await review_repo.mark_failed(review_db_id, str(e))
            raise

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