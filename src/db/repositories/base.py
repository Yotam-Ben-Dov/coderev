"""Base repository with generic CRUD operations."""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Base

# Generic type for models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing common CRUD operations.

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)
    """

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> ModelType | None:
        """Get a record by ID."""
        return await self.session.get(self.model, id)

    async def get_by_id_or_raise(self, id: int) -> ModelType:
        """Get a record by ID or raise an exception."""
        instance = await self.get_by_id(id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} with id {id} not found")
        return instance

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> Sequence[ModelType]:
        """Get all records with pagination."""
        query = select(self.model)

        # Filter out soft-deleted records if the model supports it
        if not include_deleted and hasattr(self.model, "deleted_at"):
            query = query.where(self.model.deleted_at.is_(None))  # type: ignore

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, *, include_deleted: bool = False) -> int:
        """Count all records."""
        query = select(func.count()).select_from(self.model)

        if not include_deleted and hasattr(self.model, "deleted_at"):
            query = query.where(self.model.deleted_at.is_(None))  # type: ignore

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def update(self, id: int, **kwargs: Any) -> ModelType | None:
        """Update a record by ID."""
        instance = await self.get_by_id(id)
        if instance is None:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update_many(
        self,
        filters: dict[str, Any],
        **kwargs: Any,
    ) -> int:
        """Update multiple records matching filters."""
        query = update(self.model).values(**kwargs)

        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        result = await self.session.execute(query)
        return result.rowcount  # type: ignore

    async def delete(self, id: int, *, soft: bool = True) -> bool:
        """
        Delete a record by ID.

        Args:
            id: Record ID
            soft: If True and model supports it, soft delete. Otherwise hard delete.

        Returns:
            True if record was deleted, False if not found.
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return False

        if soft and hasattr(instance, "soft_delete"):
            instance.soft_delete()  # type: ignore
            await self.session.flush()
        else:
            await self.session.delete(instance)
            await self.session.flush()

        return True

    async def restore(self, id: int) -> ModelType | None:
        """Restore a soft-deleted record."""
        instance = await self.get_by_id(id)
        if instance is None:
            return None

        if hasattr(instance, "restore"):
            instance.restore()  # type: ignore
            await self.session.flush()
            await self.session.refresh(instance)

        return instance

    async def exists(self, id: int) -> bool:
        """Check if a record exists."""
        query = select(func.count()).select_from(self.model).where(self.model.id == id)  # type: ignore
        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0
