# unreal-build

Simple build and deploy tool for Unreal Engine.

Check out `config-example.yaml` to get started.  If you don't want to install `pyyaml` package, config can also be a JSON file.

## Installation

```bash
poetry install

# Install with extras, specifying the ones you need
poetry install --extras "yaml perforce git steam"
```

### Extras
- `yaml` - for YAML config support
- `perforce` - If your project is on Perforce
- `git` - If your project is on Git
- `steam` - for Steam deployment

## Usage

```bash
poetry run unreal-build --help

# Build & Deploy
poetry run unreal-build

# Deploy only
poetry run unreal-build --no-build

# Build only
poetry run unreal-build --no-deploy

# Specify config file
poetry run unreal-build --config another_config.yaml
```
