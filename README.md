# unreal-build

Simple build tool for Unreal Engine.

Check out `config-example.yaml` to get started.  If you don't want to install `pyyaml` package, config can also be a JSON file.

## Installation

```bash
poetry install

# Install with extras, specifying the ones you need
poetry install --extras "yaml perforce git steam"
```

## Usage

```bash
poetry run unreal-build --help

# Build & Deploy
poetry run unreal-build

# Deploy only
poetry run unreal-build --no-build

# Specify config file
poetry run unreal-build --config another_config.yaml
```