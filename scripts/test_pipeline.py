"""Test the full review pipeline."""

import asyncio
import sys

from src.services.review.pipeline import ReviewPipeline


async def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python scripts/test_pipeline.py <owner> <repo> <pr_number>")
        print("Example: python scripts/test_pipeline.py octocat hello-world 123")
        sys.exit(1)

    owner = sys.argv[1]
    repo = sys.argv[2]
    pr_number = int(sys.argv[3])

    print(f"🔍 Reviewing PR #{pr_number} in {owner}/{repo}")
    print("-" * 50)

    pipeline = ReviewPipeline()

    try:
        # Set post_review=False for testing to avoid posting to GitHub
        result = await pipeline.execute(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            post_review=False,  # Change to True to actually post
        )

        print("\n✅ Review Complete!")
        print(f"   PR: #{result.pr_number} - {result.pr_title}")
        print(f"   Files Reviewed: {result.files_reviewed}")
        print(f"   Comments: {result.total_comments}")
        print(f"   Verdict: {result.verdict}")
        print(f"   Model: {result.model_used}")
        print(f"   Tokens: {result.total_tokens}")
        print(f"   Cost: ${result.total_cost_usd:.4f}")
        print(f"   Posted to GitHub: {result.review_posted}")
        print()
        print("Summary:")
        print("-" * 50)
        print(result.summary)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
