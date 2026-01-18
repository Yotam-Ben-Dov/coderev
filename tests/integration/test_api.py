"""Pytest configuration and fixtures."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment variables BEFORE importing app
os.environ.setdefault("GITHUB_TOKEN", "test-token-for-testing")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")

# Use the same database as development for local testing
# In CI, this will be overridden by environment variables
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://coderev:coderev@localhost:5432/coderev")

from src.api.main import app  # noqa: E402
from src.db.models import Base  # noqa: E402

# =============================================================================
# Event Loop Fixture
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Get the test database URL."""
    return os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://coderev:coderev@localhost:5432/coderev"
    )


@pytest.fixture(scope="session")
async def test_engine(test_db_url: str) -> AsyncGenerator[Any, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        test_db_url,
        echo=False,
        pool_pre_ping=True,
    )

    # Ensure tables exist (don't drop/recreate to preserve dev data)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Don't drop tables - we're sharing with dev database
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for each test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        # Start a transaction that will be rolled back
        await session.begin()
        yield session
        # Rollback to keep tests isolated
        await session.rollback()


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
