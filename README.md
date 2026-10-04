# Env Doctor

**Find configuration gaps before they break a fresh install or deployment.**

Env Doctor compares environment variables referenced in Python, JavaScript, TypeScript, shell, and Compose YAML files with the names in your project's `.env.example`. When a local `.env` exists, it also tells you which referenced names are absent there. Reports contain variable names and source locations, never secret values.

```text
Env Doctor: 3 variables referenced in source.

Missing from .env.example: STRIPE_SECRET_KEY
Missing from .env: DATABASE_URL
Documented but not referenced: OLD_API_TOKEN

Found in:
  STRIPE_SECRET_KEY: src/payments.py:12
```

## Run it

Requires Python 3.10 or newer. No packages to install.

```bash
python env_doctor.py path/to/project
python env_doctor.py path/to/project --write-example
python env_doctor.py path/to/project --json
```

The first command only reads files. It exits with code `1` if a referenced name is missing from `.env.example`, making it useful in CI. `--write-example` appends **empty placeholders** for missing names. It preserves existing entries, never copies values from `.env`, and is safe to run again. Review the result and add explanatory comments for each variable.

If `.env` is absent, the report says the local check was skipped. A missing `.env` is normal in CI and for people who have not set up the project yet.

## What it recognizes

| File | Examples |
| --- | --- |
| Python | `os.getenv("API_KEY")`, `os.environ["API_KEY"]`, `os.environ.get("API_KEY")` |
| JavaScript / TypeScript | `process.env.API_KEY`, `process.env["API_KEY"]`, `import.meta.env.VITE_API_URL` |
| Shell | `$API_KEY`, `${API_KEY}` |
| YAML / Docker Compose | `${DATABASE_URL}`, `${DATABASE_URL:-default}` |

Python is parsed as code, so strings and comments do not count. The JavaScript scanner ignores comments and ordinary string examples. Common dependency and build folders are skipped. Dynamic keys such as `process.env[name]` cannot be inferred; inspect those manually. Env Doctor reads root-level `.env` and `.env.example` files, and does not validate whether values are correct or safe.

## JSON and CI

`--json` returns `referenced`, `missing_from_example`, `missing_from_env`, `unused_in_example`, `env_present`, and `references` (file and line locations). The output contains no `.env` values.

```yaml
- name: Check environment contract
  run: python env_doctor.py .
```

## Development

```bash
python -m unittest discover -s tests
```

MIT licensed. Issues and pull requests are welcome, especially examples of environment syntax the scanner misses.
