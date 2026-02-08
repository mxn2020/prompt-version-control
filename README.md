# prompt-version-control

A local-first CLI tool to version prompts (and small templates), track metadata, diff versions, rollback, and export.

## Features

- **Version prompts** – store every iteration of a prompt with content, hash, tags, and notes
- **Diff** – unified diffs between any two versions
- **Rollback** – revert to any previous version (creates a new version so history is preserved)
- **Export** – dump any prompt's full history as JSON
- **Tags & notes** – annotate versions with tags and optional notes
- **Structured output** – every list/show/log command supports `--json`
- **Platform-aware storage** – SQLite database in the standard user data directory

## Quick start

```bash
# Install
pip install -e .

# Initialize the database
pv init

# Add a prompt (auto-creates the prompt if it doesn't exist)
pv add my-prompt --content "Hello {{name}}, welcome!" --tag prod --note "v1"

# Add another version
pv add my-prompt --content "Hi {{name}}, great to see you!" --tag staging

# Or read content from a file
pv add my-prompt --file prompt.txt

# List all prompts
pv list
pv list --json

# Show version history
pv log my-prompt
pv log my-prompt --json

# Show a specific version (default: latest)
pv show my-prompt
pv show my-prompt --version 1
pv show my-prompt --json

# Diff two versions
pv diff my-prompt 1 2

# Rollback to a previous version
pv rollback my-prompt 1

# Manage tags
pv tag my-prompt 1 --add deployed
pv tag my-prompt 1 --remove deployed

# Export prompt history as JSON
pv export my-prompt
pv export my-prompt --output backup.json

# Delete a prompt
pv delete my-prompt --yes
```

## Database location

By default, the database is stored in the platform-appropriate user data directory:

| Platform     | Path                                      |
|-------------|-------------------------------------------|
| Linux       | `~/.local/share/pv/pv.db`                |
| macOS       | `~/Library/Application Support/pv/pv.db`  |
| Windows     | `%APPDATA%\pv\pv.db`                      |

Override with `--db /path/to/custom.db` or the `PV_DB` environment variable.

## Development

```bash
# Install dev dependencies
pip install -e .
pip install pytest pytest-cov ruff mypy

# Run tests
pytest

# Lint
ruff check src/ tests/
ruff format --check src/ tests/

# Type check
mypy src/pv/
```

## Tech stack

- **Language:** Python 3.12
- **CLI:** Typer + Rich
- **Storage:** SQLite via SQLAlchemy 2.0
- **Migrations:** Alembic
- **Validation:** Pydantic v2
- **Testing:** pytest + pytest-cov
- **Lint/format:** ruff + mypy

## License

MIT
