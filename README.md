# Repo Tidy

Repo Tidy finds and safely fixes boring, common text-file hygiene issues:

- trailing whitespace
- missing final newlines
- mixed line endings

It is deliberately conservative. It ignores binaries and common generated/dependency directories, and it only writes changes with `--fix`.

## Use

```bash
python repo_tidy.py path/to/project
python repo_tidy.py path/to/project --fix
```

The normal check exits with status `1` when it finds issues, which makes it suitable for a simple CI check.

## Development

```bash
python -m unittest discover -s tests
```
