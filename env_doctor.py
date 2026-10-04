#!/usr/bin/env python3
"""Find environment variables used in source but missing from .env.example."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

EXCLUDED_DIRS = {".git", ".venv", "node_modules", "vendor", "dist", "build", "__pycache__"}
SOURCE_EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".yml", ".yaml"}
NAME = r"[A-Za-z_][A-Za-z0-9_]*"
JS_DOT = re.compile(rf"\b(?:process\.env|import\.meta\.env)\.({NAME})\b")
JS_BRACKET = re.compile(rf"\b(?:process\.env|import\.meta\.env)\s*\[\s*['\"]({NAME})['\"]\s*\]")
SHELL_BRACE = re.compile(rf"\$\{{({NAME})(?:(?::?[-?+])[^}}]*)?\}}")
SHELL_PLAIN = re.compile(rf"(?<!\$)\$({NAME})\b")
ENV_KEY = re.compile(rf"^\s*(?:export\s+)?({NAME})\s*=")
VITE_BUILTINS = {"MODE", "BASE_URL", "PROD", "DEV", "SSR"}


@dataclass(frozen=True)
class Report:
    referenced: list[str]
    missing_from_example: list[str]
    missing_from_env: list[str]
    unused_in_example: list[str]
    env_present: bool
    references: dict[str, list[str]]


def parse_env(path: Path) -> set[str]:
    """Read only key names; values are never returned or included in reports."""
    if not path.is_file():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = ENV_KEY.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def source_files(root: Path):
    for directory, children, files in os.walk(root):
        children[:] = [name for name in children if name.lower() not in EXCLUDED_DIRS]
        for name in files:
            path = Path(directory) / name
            if path.suffix.lower() in SOURCE_EXTENSIONS:
                yield path


def python_references(text: str):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        key = None
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os":
                key = node.args[0]
            elif isinstance(func, ast.Attribute) and func.attr == "get" and isinstance(func.value, ast.Attribute) and func.value.attr == "environ" and isinstance(func.value.value, ast.Name) and func.value.value.id == "os":
                key = node.args[0]
        elif isinstance(node, ast.Subscript):
            value = node.value
            if isinstance(value, ast.Attribute) and value.attr == "environ" and isinstance(value.value, ast.Name) and value.value.id == "os":
                key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str) and ENV_KEY.fullmatch(key.value + "="):
            yield key.value, node.lineno


def javascript_code_positions(text: str) -> list[bool]:
    """Mark positions outside comments and string literals."""
    code = [True] * len(text)
    index = 0
    state = "code"
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and next_char == "/":
                code[index] = code[index + 1] = False
                index += 2
                state = "line_comment"
                continue
            if char == "/" and next_char == "*":
                code[index] = code[index + 1] = False
                index += 2
                state = "block_comment"
                continue
            if char in ("'", '"', "`"):
                code[index] = False
                state = char
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                code[index] = False
        elif state == "block_comment":
            code[index] = False
            if char == "*" and next_char == "/":
                code[index + 1] = False
                index += 2
                state = "code"
                continue
        else:
            code[index] = False
            if char == "\\" and next_char:
                code[index + 1] = False
                index += 2
                continue
            if char == state:
                state = "code"
        index += 1
    return code


def text_references(text: str, suffix: str):
    if suffix in {".sh", ".yml", ".yaml"}:
        patterns = (SHELL_BRACE, SHELL_PLAIN)
        code_positions = None
    else:
        patterns = (JS_DOT, JS_BRACKET)
        code_positions = javascript_code_positions(text)
    for pattern in patterns:
        for match in pattern.finditer(text):
            if code_positions is not None and not code_positions[match.start()]:
                continue
            if suffix in {".sh", ".yml", ".yaml"} and text[text.rfind("\n", 0, match.start()) + 1:match.start()].lstrip().startswith("#"):
                continue
            name = match.group(1)
            if match.group(0).startswith("import.meta.env.") and name in VITE_BUILTINS:
                continue
            yield name, text.count("\n", 0, match.start()) + 1


def referenced_variables(root: Path) -> dict[str, list[str]]:
    references: dict[str, set[str]] = {}
    for path in source_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        findings = python_references(text) if path.suffix.lower() == ".py" else text_references(text, path.suffix.lower())
        for name, line in findings:
            references.setdefault(name, set()).add(f"{path.relative_to(root).as_posix()}:{line}")
    return {name: sorted(locations) for name, locations in sorted(references.items())}


def audit(root: Path) -> Report:
    references = referenced_variables(root)
    names = set(references)
    example = parse_env(root / ".env.example")
    env_present = (root / ".env").is_file()
    local = parse_env(root / ".env") if env_present else set()
    return Report(
        referenced=sorted(names),
        missing_from_example=sorted(names - example),
        missing_from_env=sorted(names - local) if env_present else [],
        unused_in_example=sorted(example - names),
        env_present=env_present,
        references=references,
    )


def update_example(root: Path, names: list[str]) -> bool:
    if not names:
        return False
    path = root / ".env.example"
    existing = path.read_bytes() if path.exists() else b""
    newline = b"\r\n" if b"\r\n" in existing and existing.count(b"\r\n") >= existing.count(b"\n") - existing.count(b"\r\n") else b"\n"
    separator = newline if existing and not existing.endswith((b"\n", b"\r")) else b""
    additions = newline.join([b"# Added by Env Doctor", *(f"{name}=".encode("ascii") for name in names)]) + newline
    with path.open("ab") as output:
        output.write(separator + additions)
    return True


def print_list(label: str, values: list[str]) -> None:
    print(f"{label}: " + (", ".join(values) if values else "none"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="project directory (default: current directory)")
    parser.add_argument("--write-example", action="store_true", help="append empty placeholders to .env.example")
    parser.add_argument("--json", action="store_true", help="write machine-readable JSON")
    args = parser.parse_args()
    root = Path(args.path).resolve()
    if not root.is_dir():
        parser.error(f"{root} is not a directory")
    report = audit(root)
    added = update_example(root, report.missing_from_example) if args.write_example else False
    if added:
        report = audit(root)
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"Env Doctor: {len(report.referenced)} variables referenced in source.\n")
        print_list("Missing from .env.example", report.missing_from_example)
        if report.env_present:
            print_list("Missing from .env", report.missing_from_env)
        else:
            print("Missing from .env: not checked (.env is absent)")
        print_list("Documented but not referenced", report.unused_in_example)
        if report.missing_from_example:
            print("\nFound in:")
            for name in report.missing_from_example:
                print(f"  {name}: {', '.join(report.references[name])}")
        if added:
            print("\nAdded empty placeholders to .env.example.")
    return 1 if report.missing_from_example else 0


if __name__ == "__main__":
    raise SystemExit(main())
