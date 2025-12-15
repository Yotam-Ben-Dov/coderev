"""Sample diffs for testing."""

SIMPLE_MODIFICATION = """diff --git a/src/main.py b/src/main.py
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

NEW_FILE = """diff --git a/src/utils.py b/src/utils.py
new file mode 100644
--- /dev/null
+++ b/src/utils.py
@@ -0,0 +1,10 @@
+def validate_input(value):
+    if value is None:
+        raise ValueError("Value cannot be None")
+    return True
+
+
+def format_output(data):
+    if not isinstance(data, dict):
+        return str(data)
+    return ", ".join(f"{k}: {v}" for k, v in data.items())
"""

MULTIPLE_FILES = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
+from src.utils import validate_input
 def main():
     print("Hello")
diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,2 +1,5 @@
 def helper():
     pass
+
+def validate_input(x):
+    return x is not None
diff --git a/tests/test_main.py b/tests/test_main.py
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -1,3 +1,6 @@
 def test_main():
-    pass
+    assert True
+
+def test_helper():
+    assert True
"""
