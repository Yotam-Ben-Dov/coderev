"""Pytest configuration and fixtures."""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# =============================================================================
# Environment Setup (must happen before app imports)
# =============================================================================

os.environ.setdefault("GITHUB_TOKEN", "test-token-for-testing")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://coderev:coderev@localhost:5432/coderev",
)

from src.api.main import app  # noqa: E402
from src.db.models import Base  # noqa: E402


# =============================================================================
# Pytest-Asyncio Configuration
# =============================================================================

pytest_plugins = ("pytest_asyncio",)


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Get the test database URL."""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://coderev:coderev@localhost:5432/coderev",
    )


@pytest.fixture(scope="function")
def test_engine_sync(test_db_url: str) -> AsyncEngine:
    """
    Create a test database engine.
    
    This is a sync fixture that returns the engine object.
    Using sync fixture avoids pytest-asyncio async generator cleanup issues.
    """
    engine = create_async_engine(
        test_db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return engine


@pytest_asyncio.fixture(scope="function")
async def test_engine(test_engine_sync: AsyncEngine) -> AsyncGenerator[AsyncEngine, None]:
    """
    Async fixture that ensures tables exist and cleans up engine.
    """
    # Ensure tables exist
    async with test_engine_sync.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine_sync

    # Dispose of the engine to clean up connections
    await test_engine_sync.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create an isolated database session for each test.

    Uses a connection-level transaction pattern:
    1. Acquires a connection from the pool
    2. Starts a transaction on the connection
    3. Binds the session to this connection
    4. After the test, rolls back the transaction (undoing all changes)

    This ensures complete test isolation without polluting the database.
    """
    # Acquire a connection from the pool
    connection = await test_engine.connect()

    # Start a transaction - this will be rolled back at the end
    transaction = await connection.begin()

    # Create a session bound to this connection
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        autoflush=False,
    )

    yield session

    # Cleanup sequence - order matters!
    # 1. Close the session (releases internal state)
    await session.close()

    # 2. Roll back the transaction (undoes all changes)
    if transaction.is_active:
        await transaction.rollback()

    # 3. Close the connection (returns to pool)
    await connection.close()


# =============================================================================
# FastAPI Test Client
# =============================================================================


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_github_response() -> dict[str, Any]:
    """Sample GitHub PR response."""
    return {
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
            "sha": "abc123def456",
            "ref": "feature-branch",
        },
        "base": {
            "sha": "def456abc123",
            "ref": "main",
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "merged_at": None,
    }


@pytest.fixture
def sample_diff() -> str:
    """Sample diff for testing."""
    return """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,7 +1,8 @@
 def calculate_sum(a, b):
-    return a + b
+    \"\"\"Calculate the sum of two numbers.\"\"\"
+    result = a + b
+    return result

 def main():
-    print(calculate_sum(1, 2))
+    print(f"Result: {calculate_sum(1, 2)}")
"""


@pytest.fixture
def sample_llm_response() -> dict[str, Any]:
    """Sample LLM review response."""
    return {
        "summary": "Good changes overall.",
        "verdict": "approve",
        "comments": [
            {
                "line": 3,
                "body": "Nice docstring!",
                "category": "DOCUMENTATION",
                "severity": "INFO",
            }
        ],
    }