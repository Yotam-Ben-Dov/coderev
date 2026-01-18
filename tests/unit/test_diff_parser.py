import pytest

from src.services.review.diff_parser import DiffParser, LineType


class TestDiffParser:
    """Tests for the diff parser."""

    @pytest.fixture
    def parser(self) -> DiffParser:
        return DiffParser()

    def test_parse_simple_modification(self, parser: DiffParser) -> None:
        """Test parsing a simple file modification."""
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,4 +1,5 @@
 def hello():
-    print("Hello")
+    print("Hello, World!")
+    return True

 hello()"""

        files = parser.parse(diff)

        assert len(files) == 1
        assert files[0].path == "src/main.py"
        assert files[0].status == "modified"
        assert len(files[0].hunks) == 1

        hunk = files[0].hunks[0]
        assert hunk.old_start == 1
        assert hunk.new_start == 1

        additions = [line for line in hunk.lines if line.type == LineType.ADDITION]
        deletions = [line for line in hunk.lines if line.type == LineType.DELETION]

        assert len(additions) == 2
        assert len(deletions) == 1
        assert additions[0].content == '    print("Hello, World!")'
        assert additions[0].new_line_no == 2

    def test_parse_new_file(self, parser: DiffParser) -> None:
        """Test parsing a newly added file."""
        diff = """diff --git a/new_file.py b/new_file.py
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,3 @@
+def new_function():
+    pass
+"""

        files = parser.parse(diff)

        assert len(files) == 1
        assert files[0].path == "new_file.py"
        assert files[0].status == "added"

    def test_parse_deleted_file(self, parser: DiffParser) -> None:
        """Test parsing a deleted file."""
        diff = """diff --git a/old_file.py b/old_file.py
--- a/old_file.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old_function():
-    pass
-"""

        files = parser.parse(diff)

        assert len(files) == 1
        assert files[0].path == "old_file.py"
        assert files[0].status == "deleted"

    def test_parse_multiple_files(self, parser: DiffParser) -> None:
        """Test parsing diff with multiple files."""
        diff = """diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,2 @@
-old line
+new line
diff --git a/file2.py b/file2.py
--- a/file2.py
+++ b/file2.py
@@ -1,2 +1,2 @@
-another old
+another new"""

        files = parser.parse(diff)

        assert len(files) == 2
        assert files[0].path == "file1.py"
        assert files[1].path == "file2.py"

    def test_parse_multiple_hunks(self, parser: DiffParser) -> None:
        """Test parsing a file with multiple hunks."""
        diff = """diff --git a/big_file.py b/big_file.py
--- a/big_file.py
+++ b/big_file.py
@@ -1,3 +1,3 @@
 def func1():
-    old1
+    new1
@@ -10,3 +10,3 @@
 def func2():
-    old2
+    new2"""

        files = parser.parse(diff)

        assert len(files) == 1
        assert len(files[0].hunks) == 2
        assert files[0].hunks[0].old_start == 1
        assert files[0].hunks[1].old_start == 10

    def test_filter_python_files(self, parser: DiffParser) -> None:
        """Test filtering to only Python files."""
        diff = """diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1 +1 @@
-old
+new
diff --git a/style.css b/style.css
--- a/style.css
+++ b/style.css
@@ -1 +1 @@
-old
+new
diff --git a/utils.py b/utils.py
--- a/utils.py
+++ b/utils.py
@@ -1 +1 @@
-old
+new"""

        files = parser.parse_and_filter_python(diff)

        assert len(files) == 2
        assert all(f.path.endswith(".py") for f in files)

    def test_get_changed_line_numbers(self, parser: DiffParser) -> None:
        """Test extracting changed line numbers."""
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,5 +1,6 @@
 line1
-line2
+line2_modified
+line2_new
 line3
 line4
-line5
+line5_modified"""

        files = parser.parse(diff)
        changed_lines = files[0].get_changed_line_numbers()

        assert 2 in changed_lines  # line2_modified
        assert 3 in changed_lines  # line2_new
        assert 6 in changed_lines  # line5_modified

    def test_empty_diff(self, parser: DiffParser) -> None:
        """Test parsing empty diff."""
        files = parser.parse("")
        assert files == []

        files = parser.parse("   \n\n  ")
        assert files == []

    def test_additions_and_deletions_count(self, parser: DiffParser) -> None:
        """Test counting additions and deletions."""
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 context
-deleted1
-deleted2
+added1
+added2
+added3"""

        files = parser.parse(diff)

        assert files[0].additions == 3
        assert files[0].deletions == 2
