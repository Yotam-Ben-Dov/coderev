"""Test LLM integration manually."""

import asyncio

from src.services.llm.base import ReviewRequest
from src.services.llm.router import LLMRouter

SAMPLE_DIFF = """@@ -1,10 +1,15 @@
 def calculate_total(items):
-    total = 0
-    for item in items:
-        total += item
-    return total
+    \"\"\"Calculate the total of all items.\"\"\"
+    if not items:
+        return 0
+    total = sum(items)
+    return total
+
+
+def calculate_average(items):
+    total = calculate_total(items)
+    return total / len(items)
"""


async def main() -> None:
    router = LLMRouter()

    print("Available providers:", router.get_available_providers())
    print()

    request = ReviewRequest(
        diff=SAMPLE_DIFF,
        file_path="src/calculator.py",
        pr_title="Refactor calculator functions",
        pr_description="Improved calculate_total and added calculate_average",
    )

    print("Sending review request...")
    print("-" * 50)

    try:
        response = await router.review_code(request)

        print(f"Model: {response.model}")
        print(f"Verdict: {response.verdict}")
        print(f"Tokens: {response.tokens_used}")
        print(f"Cost: ${response.cost_usd:.4f}")
        print()
        print("Summary:")
        print(response.summary)
        print()
        print("Comments:")
        for comment in response.comments:
            print(f"  Line {comment.line} [{comment.category.value}] ({comment.severity.value}):")
            print(f"    {comment.body}")
            print()

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
