import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class LineType(str, Enum):
    CONTEXT = "context"
    ADDITION = "addition"
    DELETION = "deletion"


@dataclass
class DiffLine:
    """A single line in a diff."""

    type: LineType
    content: str
    old_line_no: int | None = None
    new_line_no: int | None = None

    def __str__(self) -> str:
        prefix = {
            LineType.CONTEXT: " ",
            LineType.ADDITION: "+",
            LineType.DELETION: "-",
        }[self.type]
        return f"{prefix}{self.content}"


@dataclass
class Hunk:
    """A hunk (section) of changes in a diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str  # The @@ line
    lines: list[DiffLine] = field(default_factory=list)

    def get_new_line_numbers(self) -> list[int]:
        """Get all new file line numbers that have additions."""
        return [
            line.new_line_no
            for line in self.lines
            if line.type == LineType.ADDITION and line.new_line_no is not None
        ]


@dataclass
class FileDiff:
    """Parsed diff for a single file."""

    path: str
    status: Literal["added", "modified", "deleted", "renamed"]
    old_path: str | None = None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def additions(self) -> int:
        """Count of added lines."""
        return sum(
            1 for hunk in self.hunks for line in hunk.lines if line.type == LineType.ADDITION
        )

    @property
    def deletions(self) -> int:
        """Count of deleted lines."""
        return sum(
            1 for hunk in self.hunks for line in hunk.lines if line.type == LineType.DELETION
        )

    def to_patch_string(self) -> str:
        """Reconstruct the patch string for this file."""
        lines = []
        for hunk in self.hunks:
            lines.append(hunk.header)
            for diff_line in hunk.lines:
                lines.append(str(diff_line))
        return "\n".join(lines)

    def get_changed_line_numbers(self) -> list[int]:
        """Get all line numbers in the new file that have changes."""
        line_numbers = []
        for hunk in self.hunks:
            line_numbers.extend(hunk.get_new_line_numbers())
        return sorted(set(line_numbers))


class DiffParser:
    """Parser for unified diff format."""

    # Regex patterns
    FILE_HEADER_PATTERN = re.compile(r"^diff --git a/(.*) b/(.*)$")
    OLD_FILE_PATTERN = re.compile(r"^--- (?:a/)?(.*)$")
    NEW_FILE_PATTERN = re.compile(r"^\+\+\+ (?:b/)?(.*)$")
    HUNK_HEADER_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")

    def parse(self, diff_text: str) -> list[FileDiff]:
        """Parse a unified diff into structured FileDiff objects."""
        if not diff_text.strip():
            return []

        files: list[FileDiff] = []
        current_file: FileDiff | None = None
        current_hunk: Hunk | None = None
        old_line_no = 0
        new_line_no = 0

        lines = diff_text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # New file diff starting
            file_match = self.FILE_HEADER_PATTERN.match(line)
            if file_match:
                if current_file:
                    files.append(current_file)

                old_path = file_match.group(1)
                new_path = file_match.group(2)

                current_file = FileDiff(
                    path=new_path,
                    status="modified",  # Will be updated based on --- and +++ lines
                    old_path=old_path if old_path != new_path else None,
                )
                current_hunk = None
                i += 1
                continue

            # Old file line (--- a/file)
            old_match = self.OLD_FILE_PATTERN.match(line)
            if old_match and current_file:
                if old_match.group(1) == "/dev/null":
                    current_file.status = "added"
                i += 1
                continue

            # New file line (+++ b/file)
            new_match = self.NEW_FILE_PATTERN.match(line)
            if new_match and current_file:
                if new_match.group(1) == "/dev/null":
                    current_file.status = "deleted"
                elif current_file.old_path:
                    current_file.status = "renamed"
                i += 1
                continue

            # Hunk header
            hunk_match = self.HUNK_HEADER_PATTERN.match(line)
            if hunk_match and current_file:
                old_start = int(hunk_match.group(1))
                old_count = int(hunk_match.group(2) or 1)
                new_start = int(hunk_match.group(3))
                new_count = int(hunk_match.group(4) or 1)

                current_hunk = Hunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    header=line,
                )
                current_file.hunks.append(current_hunk)

                old_line_no = old_start
                new_line_no = new_start
                i += 1
                continue

            # Diff content lines
            if current_hunk is not None and line:
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk.lines.append(
                        DiffLine(
                            type=LineType.ADDITION,
                            content=line[1:],
                            new_line_no=new_line_no,
                        )
                    )
                    new_line_no += 1
                elif line.startswith("-") and not line.startswith("---"):
                    current_hunk.lines.append(
                        DiffLine(
                            type=LineType.DELETION,
                            content=line[1:],
                            old_line_no=old_line_no,
                        )
                    )
                    old_line_no += 1
                elif line.startswith(" "):
                    current_hunk.lines.append(
                        DiffLine(
                            type=LineType.CONTEXT,
                            content=line[1:],
                            old_line_no=old_line_no,
                            new_line_no=new_line_no,
                        )
                    )
                    old_line_no += 1
                    new_line_no += 1
                elif line.startswith("\\"):
                    # "\ No newline at end of file" - skip
                    pass

            i += 1

        # Don't forget the last file
        if current_file:
            files.append(current_file)

        return files

    def filter_python_files(self, files: list[FileDiff]) -> list[FileDiff]:
        """Filter to only Python files."""
        return [f for f in files if f.path.endswith(".py")]

    def parse_and_filter_python(self, diff_text: str) -> list[FileDiff]:
        """Parse diff and return only Python files."""
        all_files = self.parse(diff_text)
        return self.filter_python_files(all_files)
