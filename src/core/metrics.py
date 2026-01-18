"""
Prometheus metrics for CodeRev.

This module provides:
- HTTP request metrics (latency, count, errors)
- LLM metrics (tokens, cost, latency per model/provider)
- Database metrics (connection pool, query latency)
- Task queue metrics (Celery task counts, durations)
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# =============================================================================
# Application Info
# =============================================================================

APP_INFO = Info(
    "coderev_app",
    "CodeRev application information",
)

# =============================================================================
# HTTP Request Metrics
# =============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "coderev_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "coderev_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "coderev_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "endpoint"],
)

# =============================================================================
# LLM Metrics
# =============================================================================

LLM_REQUESTS_TOTAL = Counter(
    "coderev_llm_requests_total",
    "Total number of LLM API requests",
    ["provider", "model", "status"],  # status: success, error, timeout
)

LLM_TOKENS_TOTAL = Counter(
    "coderev_llm_tokens_total",
    "Total number of tokens processed",
    ["provider", "model", "direction"],  # direction: input, output
)

LLM_COST_USD_TOTAL = Counter(
    "coderev_llm_cost_usd_total",
    "Total cost in USD for LLM API calls",
    ["provider", "model"],
)

LLM_REQUEST_DURATION_SECONDS = Histogram(
    "coderev_llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0),
)

LLM_PROMPT_TOKENS = Histogram(
    "coderev_llm_prompt_tokens",
    "Distribution of prompt token counts",
    ["provider", "model"],
    buckets=(100, 500, 1000, 2500, 5000, 10000, 25000, 50000),
)

LLM_COMPLETION_TOKENS = Histogram(
    "coderev_llm_completion_tokens",
    "Distribution of completion token counts",
    ["provider", "model"],
    buckets=(50, 100, 250, 500, 1000, 2000, 4000),
)

# =============================================================================
# Review Metrics
# =============================================================================

REVIEWS_TOTAL = Counter(
    "coderev_reviews_total",
    "Total number of code reviews processed",
    [
        "repository",
        "status",
        "verdict",
    ],  # status: completed, failed; verdict: approve, request_changes, comment
)

REVIEWS_IN_PROGRESS = Gauge(
    "coderev_reviews_in_progress",
    "Number of reviews currently being processed",
)

REVIEW_DURATION_SECONDS = Histogram(
    "coderev_review_duration_seconds",
    "Total review duration in seconds (end-to-end)",
    ["repository"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

REVIEW_FILES_ANALYZED = Histogram(
    "coderev_review_files_analyzed",
    "Number of files analyzed per review",
    buckets=(1, 2, 5, 10, 20, 50),
)

REVIEW_COMMENTS_GENERATED = Histogram(
    "coderev_review_comments_generated",
    "Number of comments generated per review",
    ["severity"],  # critical, warning, info, suggestion
    buckets=(0, 1, 2, 5, 10, 20, 50),
)

# =============================================================================
# GitHub API Metrics
# =============================================================================

GITHUB_API_REQUESTS_TOTAL = Counter(
    "coderev_github_api_requests_total",
    "Total number of GitHub API requests",
    ["endpoint", "method", "status_code"],
)

GITHUB_API_DURATION_SECONDS = Histogram(
    "coderev_github_api_duration_seconds",
    "GitHub API request duration in seconds",
    ["endpoint", "method"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

GITHUB_RATE_LIMIT_REMAINING = Gauge(
    "coderev_github_rate_limit_remaining",
    "Remaining GitHub API rate limit",
)

GITHUB_RATE_LIMIT_RESET_SECONDS = Gauge(
    "coderev_github_rate_limit_reset_seconds",
    "Seconds until GitHub rate limit resets",
)

# =============================================================================
# Database Metrics
# =============================================================================

DB_CONNECTIONS_ACTIVE = Gauge(
    "coderev_db_connections_active",
    "Number of active database connections",
)

DB_CONNECTIONS_IDLE = Gauge(
    "coderev_db_connections_idle",
    "Number of idle database connections in pool",
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "coderev_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],  # select, insert, update, delete
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# =============================================================================
# Celery Task Metrics
# =============================================================================

CELERY_TASKS_TOTAL = Counter(
    "coderev_celery_tasks_total",
    "Total number of Celery tasks",
    ["task_name", "status"],  # status: started, succeeded, failed, retried
)

CELERY_TASK_DURATION_SECONDS = Histogram(
    "coderev_celery_task_duration_seconds",
    "Celery task duration in seconds",
    ["task_name"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

CELERY_QUEUE_LENGTH = Gauge(
    "coderev_celery_queue_length",
    "Number of tasks waiting in Celery queue",
    ["queue_name"],
)


# =============================================================================
# Helper Functions
# =============================================================================


def initialize_app_info(version: str, environment: str) -> None:
    """Initialize application info metric."""
    APP_INFO.info(
        {
            "version": version,
            "environment": environment,
        }
    )


def record_llm_request(
    provider: str,
    model: str,
    status: str,
    duration_seconds: float,
    tokens_input: int = 0,
    tokens_output: int = 0,
    cost_usd: float = 0.0,
) -> None:
    """
    Record metrics for an LLM API request.

    Args:
        provider: LLM provider name (anthropic, openai, ollama)
        model: Model identifier
        status: Request status (success, error, timeout)
        duration_seconds: Request duration
        tokens_input: Number of input/prompt tokens
        tokens_output: Number of output/completion tokens
        cost_usd: Estimated cost in USD
    """
    LLM_REQUESTS_TOTAL.labels(
        provider=provider,
        model=model,
        status=status,
    ).inc()

    LLM_REQUEST_DURATION_SECONDS.labels(
        provider=provider,
        model=model,
    ).observe(duration_seconds)

    if tokens_input > 0:
        LLM_TOKENS_TOTAL.labels(
            provider=provider,
            model=model,
            direction="input",
        ).inc(tokens_input)

        LLM_PROMPT_TOKENS.labels(
            provider=provider,
            model=model,
        ).observe(tokens_input)

    if tokens_output > 0:
        LLM_TOKENS_TOTAL.labels(
            provider=provider,
            model=model,
            direction="output",
        ).inc(tokens_output)

        LLM_COMPLETION_TOKENS.labels(
            provider=provider,
            model=model,
        ).observe(tokens_output)

    if cost_usd > 0:
        LLM_COST_USD_TOTAL.labels(
            provider=provider,
            model=model,
        ).inc(cost_usd)


def record_review_completed(
    repository: str,
    status: str,
    verdict: str,
    duration_seconds: float,
    files_analyzed: int,
    comments_by_severity: dict[str, int],
) -> None:
    """
    Record metrics for a completed review.

    Args:
        repository: Repository full name (owner/repo)
        status: Review status (completed, failed)
        verdict: Review verdict (approve, request_changes, comment)
        duration_seconds: Total review duration
        files_analyzed: Number of files analyzed
        comments_by_severity: Dict mapping severity to comment count
    """
    REVIEWS_TOTAL.labels(
        repository=repository,
        status=status,
        verdict=verdict,
    ).inc()

    REVIEW_DURATION_SECONDS.labels(
        repository=repository,
    ).observe(duration_seconds)

    REVIEW_FILES_ANALYZED.observe(files_analyzed)

    for severity, count in comments_by_severity.items():
        REVIEW_COMMENTS_GENERATED.labels(
            severity=severity,
        ).observe(count)


def record_github_api_call(
    endpoint: str,
    method: str,
    status_code: int,
    duration_seconds: float,
    rate_limit_remaining: int | None = None,
    rate_limit_reset: int | None = None,
) -> None:
    """
    Record metrics for a GitHub API call.

    Args:
        endpoint: API endpoint (e.g., "pulls", "reviews")
        method: HTTP method
        status_code: Response status code
        duration_seconds: Request duration
        rate_limit_remaining: Remaining rate limit (if available)
        rate_limit_reset: Rate limit reset timestamp (if available)
    """
    GITHUB_API_REQUESTS_TOTAL.labels(
        endpoint=endpoint,
        method=method,
        status_code=str(status_code),
    ).inc()

    GITHUB_API_DURATION_SECONDS.labels(
        endpoint=endpoint,
        method=method,
    ).observe(duration_seconds)

    if rate_limit_remaining is not None:
        GITHUB_RATE_LIMIT_REMAINING.set(rate_limit_remaining)

    if rate_limit_reset is not None:
        import time

        reset_in_seconds = max(0, rate_limit_reset - int(time.time()))
        GITHUB_RATE_LIMIT_RESET_SECONDS.set(reset_in_seconds)
