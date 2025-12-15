"""Quick script to test GitHub integration."""

import asyncio

from src.services.github.client import GitHubClient


async def main():
    client = GitHubClient()

    # Replace with a real public repo and PR you can access
    # Using a popular open-source repo as example
    owner = "fastapi"
    repo = "fastapi"
    pr_number = 1  # Pick any open PR

    try:
        pr = await client.get_pull_request(owner, repo, pr_number)
        print(f"✓ PR #{pr.number}: {pr.title}")
        print(f"  State: {pr.state}")
        print(f"  Author: {pr.user.login}")

        files = await client.get_pull_request_files(owner, repo, pr_number)
        print(f"  Files changed: {len(files)}")
        for f in files[:3]:
            print(f"    - {f.filename} ({f.status.value})")

    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
