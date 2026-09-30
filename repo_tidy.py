#!/usr/bin/env python3
"""Find and safely repair common text-file hygiene problems."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXCLUDED_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
TEXT_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".css", ".go", ".h", ".html", ".java", ".js", ".json",
    ".md", ".py", ".rb", ".rs", ".sh", ".sql", ".toml", ".ts", ".tsx", ".txt",
    ".xml", ".yaml", ".yml",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    trailing_whitespace_lines: tuple[int, ...]
    missing_final_newline: bool
    mixed_line_endings: bool

    @property
    def has_issues(self) -> bool:
        return bool(
            self.trailing_whitespace_lines
            or self.missing_final_newline
            or self.mixed_line_endings
        )


def is_candidate(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS


def inspect(path: Path) -> Finding | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None

    if b"\x00" in raw:
        return None

    text = raw.decode("utf-8", errors="strict")
    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    line_breaks = crlf_count + lf_count
    mixed = crlf_count > 0 and lf_count > 0
    lines = text.splitlines()
    trailing = tuple(
        number
        for number, line in enumerate(lines, start=1)
        if line.rstrip(" \t") != line
    )
    missing_final_newline = bool(text) and not text.endswith(("\n", "\r"))

    if not (trailing or missing_final_newline or mixed):
        return Finding(path, (), False, False) if line_breaks == 0 else Finding(path, (), False, False)
    return Finding(path, trailing, missing_final_newline, mixed)


def repaired_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    newline = "\r\n" if text.count("\r\n") > text.count("\n") - text.count("\r\n") else "\n"
    normalized_lines = [line.rstrip(" \t") for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while len(normalized_lines) > 1 and normalized_lines[-1] == "" and normalized_lines[-2] == "":
        normalized_lines.pop()
    return newline.join(normalized_lines).rstrip(newline) + newline


def walk(root: Path):
    for path in root.rglob("*"):
        if any(part in DEFAULT_EXCLUDED_DIRS for part in path.parts):
            continue
        if is_candidate(path):
            yield path


def describe(finding: Finding) -> str:
    problems: list[str] = []
    if finding.trailing_whitespace_lines:
        lines = ", ".join(map(str, finding.trailing_whitespace_lines[:8]))
        suffix = "…" if len(finding.trailing_whitespace_lines) > 8 else ""
        problems.append(f"trailing whitespace on line(s) {lines}{suffix}")
    if finding.missing_final_newline:
        problems.append("missing final newline")
    if finding.mixed_line_endings:
        problems.append("mixed line endings")
    return "; ".join(problems)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="directory to inspect (default: current directory)")
    parser.add_argument("--fix", action="store_true", help="apply safe whitespace/newline repairs")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        parser.error(f"{root} is not a directory")

    findings = [finding for file in walk(root) if (finding := inspect(file)) and finding.has_issues]
    if not findings:
        print("Repo Tidy: no issues found.")
        return 0

    for finding in findings:
        relative = finding.path.relative_to(root)
        if args.fix:
            finding.path.write_text(repaired_text(finding.path), encoding="utf-8", newline="")
            print(f"fixed  {relative}: {describe(finding)}")
        else:
            print(f"found  {relative}: {describe(finding)}")

    if not args.fix:
        print(f"\n{len(findings)} file(s) need attention. Re-run with --fix to repair them.")
        return 1
    print(f"\nFixed {len(findings)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
