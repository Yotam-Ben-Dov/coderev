"""Repository for GitHub repositories (meta, I know)."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Repository
from src.db.repositories.base import BaseRepository


class RepositoryRepository(BaseRepository[Repository]):
    """Repository for Repository model operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Repository, session)

    async def get_by_full_name(self, full_name: str) -> Repository | None:
        """Get a repository by its full name (owner/repo)."""
        query = select(Repository).where(
            Repository.full_name == full_name,
            Repository.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_owner_and_name(
        self,
        owner: str,
        name: str,
    ) -> Repository | None:
        """Get a repository by owner and name."""
        query = select(Repository).where(
            Repository.owner == owner,
            Repository.name == name,
            Repository.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        owner: str,
        name: str,
        github_id: int | None = None,
    ) -> tuple[Repository, bool]:
        """
        Get an existing repository or create a new one.

        Returns:
            Tuple of (repository, created) where created is True if new.
        """
        existing = await self.get_by_owner_and_name(owner, name)
        if existing:
            return existing, False

        repo = await self.create(
            owner=owner,
            name=name,
            full_name=f"{owner}/{name}",
            github_id=github_id,
        )
        return repo, True

    async def get_by_github_id(self, github_id: int) -> Repository | None:
        """Get a repository by its GitHub ID."""
        query = select(Repository).where(
            Repository.github_id == github_id,
            Repository.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner: str) -> Sequence[Repository]:
        """List all repositories for an owner."""
        query = (
            select(Repository)
            .where(
                Repository.owner == owner,
                Repository.deleted_at.is_(None),
            )
            .order_by(Repository.name)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_settings(
        self,
        id: int,
        settings: dict,
    ) -> Repository | None:
        """Update repository settings."""
        repo = await self.get_by_id(id)
        if repo is None:
            return None

        # Merge settings
        current_settings = repo.settings or {}
        current_settings.update(settings)
        repo.settings = current_settings

        await self.session.flush()
        await self.session.refresh(repo)
        return repo
