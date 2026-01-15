"""Tests for database repositories."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ReviewStatus
from src.db.repositories import RepositoryRepository, ReviewRepository, ReviewCommentRepository


class TestRepositoryRepository:
    """Tests for RepositoryRepository."""

    @pytest.mark.asyncio
    async def test_create_repository(self, db_session: AsyncSession) -> None:
        """Test creating a repository."""
        repo = RepositoryRepository(db_session)
        
        result = await repo.create(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
        )
        
        assert result.id is not None
        assert result.owner == "testowner"
        assert result.name == "testrepo"
        assert result.full_name == "testowner/testrepo"

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, db_session: AsyncSession) -> None:
        """Test get_or_create returns existing repository."""
        repo = RepositoryRepository(db_session)
        
        # Create first
        created, was_created = await repo.get_or_create("owner1", "repo1")
        assert was_created is True
        
        # Get existing
        existing, was_created = await repo.get_or_create("owner1", "repo1")
        assert was_created is False
        assert existing.id == created.id

    @pytest.mark.asyncio
    async def test_get_by_full_name(self, db_session: AsyncSession) -> None:
        """Test getting repository by full name."""
        repo = RepositoryRepository(db_session)
        
        await repo.create(
            owner="myowner",
            name="myrepo",
            full_name="myowner/myrepo",
        )
        
        result = await repo.get_by_full_name("myowner/myrepo")
        assert result is not None
        assert result.full_name == "myowner/myrepo"

    @pytest.mark.asyncio
    async def test_soft_delete(self, db_session: AsyncSession) -> None:
        """Test soft delete functionality."""
        repo = RepositoryRepository(db_session)
        
        created = await repo.create(
            owner="deletetest",
            name="repo",
            full_name="deletetest/repo",
        )
        
        # Soft delete
        deleted = await repo.delete(created.id, soft=True)
        assert deleted is True
        
        # Should not be found in normal queries
        result = await repo.get_by_full_name("deletetest/repo")
        assert result is None


class TestReviewRepository:
    """Tests for ReviewRepository."""

    @pytest.mark.asyncio
    async def test_create_review(self, db_session: AsyncSession) -> None:
        """Test creating a review."""
        # First create a repository
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="test",
            name="repo",
            full_name="test/repo",
        )
        
        review_repo = ReviewRepository(db_session)
        review = await review_repo.create(
            repository_id=repository.id,
            pr_number=42,
            pr_title="Test PR",
            head_sha="abc123",
            status=ReviewStatus.PENDING.value,
        )
        
        assert review.id is not None
        assert review.pr_number == 42
        assert review.status == ReviewStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_mark_completed(self, db_session: AsyncSession) -> None:
        """Test marking a review as completed."""
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="test2",
            name="repo2",
            full_name="test2/repo2",
        )
        
        review_repo = ReviewRepository(db_session)
        review = await review_repo.create(
            repository_id=repository.id,
            pr_number=1,
            pr_title="Test",
            head_sha="def456",
            status=ReviewStatus.PENDING.value,
        )
        
        updated = await review_repo.mark_completed(
            review.id,
            verdict="approve",
            summary="LGTM!",
            files_reviewed=3,
            total_comments=5,
            model_used="test-model",
            tokens_input=100,
            tokens_output=50,
            cost_usd=0.01,
            latency_ms=1500,
        )
        
        assert updated is not None
        assert updated.status == ReviewStatus.COMPLETED.value
        assert updated.verdict == "approve"
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_get_by_sha(self, db_session: AsyncSession) -> None:
        """Test getting a review by commit SHA."""
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="test3",
            name="repo3",
            full_name="test3/repo3",
        )
        
        review_repo = ReviewRepository(db_session)
        await review_repo.create(
            repository_id=repository.id,
            pr_number=10,
            pr_title="SHA Test",
            head_sha="unique_sha_123",
            status=ReviewStatus.COMPLETED.value,
        )
        
        result = await review_repo.get_by_sha(repository.id, "unique_sha_123")
        assert result is not None
        assert result.head_sha == "unique_sha_123"

    @pytest.mark.asyncio
    async def test_exists_for_sha(self, db_session: AsyncSession) -> None:
        """Test checking if review exists for SHA."""
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="test4",
            name="repo4",
            full_name="test4/repo4",
        )
        
        review_repo = ReviewRepository(db_session)
        await review_repo.create(
            repository_id=repository.id,
            pr_number=20,
            pr_title="Exists Test",
            head_sha="exists_sha_456",
            status=ReviewStatus.COMPLETED.value,
        )
        
        exists = await review_repo.exists_for_sha(repository.id, "exists_sha_456")
        assert exists is True
        
        not_exists = await review_repo.exists_for_sha(repository.id, "nonexistent_sha")
        assert not_exists is False

    @pytest.mark.asyncio
    async def test_get_stats(self, db_session: AsyncSession) -> None:
        """Test getting review statistics."""
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="stats",
            name="repo",
            full_name="stats/repo",
        )
        
        review_repo = ReviewRepository(db_session)
        
        # Create some reviews
        for i in range(3):
            review = await review_repo.create(
                repository_id=repository.id,
                pr_number=i + 1,
                pr_title=f"PR {i + 1}",
                head_sha=f"sha_{i}",
                status=ReviewStatus.PENDING.value,
            )
            await review_repo.mark_completed(
                review.id,
                verdict="approve",
                summary="Good",
                files_reviewed=2,
                total_comments=3,
                model_used="test-model",
                tokens_input=100,
                tokens_output=50,
                cost_usd=0.01,
                latency_ms=1000,
            )
        
        stats = await review_repo.get_stats(repository_id=repository.id, days=30)
        
        assert stats["total_reviews"] == 3
        assert stats["total_cost_usd"] == pytest.approx(0.03, rel=0.01)


class TestReviewCommentRepository:
    """Tests for ReviewCommentRepository."""

    @pytest.mark.asyncio
    async def test_create_many(self, db_session: AsyncSession) -> None:
        """Test creating multiple comments at once."""
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="comments",
            name="repo",
            full_name="comments/repo",
        )
        
        review_repo = ReviewRepository(db_session)
        review = await review_repo.create(
            repository_id=repository.id,
            pr_number=1,
            pr_title="Comments Test",
            head_sha="comment_sha",
            status=ReviewStatus.COMPLETED.value,
        )
        
        comment_repo = ReviewCommentRepository(db_session)
        comments = await comment_repo.create_many(
            review.id,
            [
                {
                    "file_path": "src/main.py",
                    "line_number": 10,
                    "body": "First comment",
                    "category": "bug",
                    "severity": "warning",
                },
                {
                    "file_path": "src/main.py",
                    "line_number": 20,
                    "body": "Second comment",
                    "category": "suggestion",
                    "severity": "info",
                },
            ],
        )
        
        assert len(comments) == 2
        assert comments[0].body == "First comment"
        assert comments[1].body == "Second comment"

    @pytest.mark.asyncio
    async def test_get_by_review(self, db_session: AsyncSession) -> None:
        """Test getting comments by review ID."""
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="getcomments",
            name="repo",
            full_name="getcomments/repo",
        )
        
        review_repo = ReviewRepository(db_session)
        review = await review_repo.create(
            repository_id=repository.id,
            pr_number=2,
            pr_title="Get Comments Test",
            head_sha="get_comment_sha",
            status=ReviewStatus.COMPLETED.value,
        )
        
        comment_repo = ReviewCommentRepository(db_session)
        await comment_repo.create_many(
            review.id,
            [
                {
                    "file_path": "file1.py",
                    "line_number": 5,
                    "body": "Comment 1",
                    "category": "style",
                    "severity": "info",
                },
                {
                    "file_path": "file2.py",
                    "line_number": 15,
                    "body": "Comment 2",
                    "category": "bug",
                    "severity": "critical",
                },
            ],
        )
        
        comments = await comment_repo.get_by_review(review.id)
        assert len(comments) == 2

    @pytest.mark.asyncio
    async def test_count_by_severity(self, db_session: AsyncSession) -> None:
        """Test counting comments by severity."""
        repo_repo = RepositoryRepository(db_session)
        repository = await repo_repo.create(
            owner="severity",
            name="repo",
            full_name="severity/repo",
        )
        
        review_repo = ReviewRepository(db_session)
        review = await review_repo.create(
            repository_id=repository.id,
            pr_number=3,
            pr_title="Severity Test",
            head_sha="severity_sha",
            status=ReviewStatus.COMPLETED.value,
        )
        
        comment_repo = ReviewCommentRepository(db_session)
        await comment_repo.create_many(
            review.id,
            [
                {"file_path": "f.py", "line_number": 1, "body": "c1", "category": "bug", "severity": "critical"},
                {"file_path": "f.py", "line_number": 2, "body": "c2", "category": "bug", "severity": "critical"},
                {"file_path": "f.py", "line_number": 3, "body": "c3", "category": "style", "severity": "info"},
            ],
        )
        
        counts = await comment_repo.count_by_severity(review.id)
        
        assert counts.get("critical") == 2
        assert counts.get("info") == 1