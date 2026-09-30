import tempfile
import unittest
from pathlib import Path

from repo_tidy import inspect, repaired_text


class RepoTidyTests(unittest.TestCase):
    def test_detects_common_hygiene_issues(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_bytes(b"answer = 42  \r\nprint(answer)\nlast")
            finding = inspect(path)
            self.assertEqual(finding.trailing_whitespace_lines, (1,))
            self.assertTrue(finding.missing_final_newline)
            self.assertTrue(finding.mixed_line_endings)

    def test_repair_normalizes_and_adds_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.txt"
            path.write_text("one  \n two\t", encoding="utf-8")
            self.assertEqual(repaired_text(path), "one\n two\n")


if __name__ == "__main__":
    unittest.main()
