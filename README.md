# Env Doctor

Env Doctor keeps a project's environment-variable contract honest. It scans Python, JavaScript, TypeScript, Docker Compose, and shell files, then compares what the code uses with `.env` and `.env.example`.

It answers the questions that regularly slow down local setup and deployment:

- Which variables does the app use but fail to document?
- Which documented variables are absent from my local `.env`?
- Which `.env.example` entries are no longer used?
- Can I update the example file without exposing secrets? (Yes—Env Doctor writes empty placeholders only.)

## Quick start

```bash
python env_doctor.py .
python env_doctor.py . --write-example
python env_doctor.py . --json
```

The default command is read-only. `--write-example` appends only missing variable names to `.env.example`; it never copies values from `.env` and never removes existing entries.

## Example output

```text
Env Doctor: 7 variables referenced in source.

Missing from .env.example: STRIPE_SECRET_KEY
Missing from .env: DATABASE_URL
Documented but not referenced: OLD_API_TOKEN
```

## Development

```bash
python -m unittest discover -s tests
```
