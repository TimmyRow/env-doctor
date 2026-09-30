#!/usr/bin/env python3
"""Audit environment-variable usage and safely maintain .env.example."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

EXCLUDED_DIRS = {".git", ".venv", "node_modules", "vendor", "dist", "build", "__pycache__"}
SOURCE_EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".yml", ".yaml"}
PATTERNS = (
    re.compile(r"(?:os\.getenv|os\.environ\.get)\(\s*['\\\"]([A-Z][A-Z0-9_]*)['\\\"]"),
    re.compile(r"os\.environ\[\s*['\\\"]([A-Z][A-Z0-9_]*)['\\\"]\s*\]"),
    re.compile(r"(?:process\.env|import\.meta\.env)\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"(?:process\.env|import\.meta\.env)\[\s*['\\\"]([A-Z][A-Z0-9_]*)['\\\"]\s*\]"),
    re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-[^}]*)?\}"),
)
ENV_KEY = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=")


@dataclass(frozen=True)
class Report:
    referenced: list[str]
    missing_from_example: list[str]
    missing_from_env: list[str]
    unused_in_example: list[str]


def parse_env(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = ENV_KEY.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def source_files(root: Path):
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
            yield path


def referenced_variables(root: Path) -> set[str]:
    names: set[str] = set()
    for path in source_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in PATTERNS:
            names.update(pattern.findall(text))
    return names


def audit(root: Path) -> Report:
    referenced = referenced_variables(root)
    example = parse_env(root / ".env.example")
    local = parse_env(root / ".env")
    return Report(
        referenced=sorted(referenced),
        missing_from_example=sorted(referenced - example),
        missing_from_env=sorted(referenced - local) if (root / ".env").is_file() else [],
        unused_in_example=sorted(example - referenced),
    )


def update_example(root: Path, names: list[str]) -> bool:
    if not names:
        return False
    path = root / ".env.example"
    prefix = path.read_text(encoding="utf-8") if path.exists() else ""
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    addition = "# Added by Env Doctor\n" + "\n".join(f"{name}=" for name in names) + "\n"
    path.write_text(prefix + addition, encoding="utf-8")
    return True


def print_list(label: str, values: list[str]) -> None:
    print(f"{label}: " + (", ".join(values) if values else "none"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="project directory (default: current directory)")
    parser.add_argument("--write-example", action="store_true", help="append missing empty placeholders to .env.example")
    parser.add_argument("--json", action="store_true", help="write machine-readable JSON")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        parser.error(f"{root} is not a directory")
    report = audit(root)
    if args.write_example:
        update_example(root, report.missing_from_example)
        report = audit(root)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"Env Doctor: {len(report.referenced)} variables referenced in source.\n")
        print_list("Missing from .env.example", report.missing_from_example)
        print_list("Missing from .env", report.missing_from_env)
        print_list("Documented but not referenced", report.unused_in_example)
        if args.write_example:
            print("\nUpdated .env.example with empty placeholders where needed.")

    return 1 if report.missing_from_example else 0


if __name__ == "__main__":
    raise SystemExit(main())
