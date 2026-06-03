# Installation

## Recommended: pipx (isolated CLI)

```bash
pipx install grok-build-cli-utilities
```

`pipx` gives you an isolated environment and puts `grok-utils` directly on your PATH. Ideal for CLI tools.

## pip (global or virtualenv)

```bash
pip install grok-build-cli-utilities
```

## From source (development / latest)

```bash
git clone https://github.com/cobusgreyling/grok-build-cli-utilities.git
cd grok-build-cli-utilities
pip install -e ".[dev]"
```

After editable install you can run `grok-utils` (ensure the Python user scripts dir or venv bin is on PATH).

You can also run directly:

```bash
python -m pip install -e ".[dev]"
python -m grok_build_cli_utilities --help   # or use the entrypoint
```

## Verify

```bash
grok-utils --version
grok-utils --help
grok-utils doctor
```

## Using with a non-default Grok home

All commands support:

```bash
grok-utils --grok-home /path/to/.grok ...
# or
GROK_HOME=/path/to/.grok grok-utils ...
```

## Updating

```bash
pipx upgrade grok-build-cli-utilities
# or
pip install --upgrade grok-build-cli-utilities
```

## Optional: docs extras (for contributors)

```bash
pip install -e ".[docs]"
mkdocs serve
```

See [Development](development.md) for the full workflow.
