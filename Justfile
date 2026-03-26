set shell := ["bash", "-cu"]

port := env_var_or_default("PORT", "8000")

# Show available recipes
_default:
    @just --list

# Install project tooling/dependencies
up:
    uv sync

# Generate deprecations data and feeds
generate:
    python run.py

# Serve docs locally
server:
    cd docs && python -m http.server {{port}}

# Run tests
test:
    pytest .

# Auto-fix lint/format issues
format:
    ruff check --fix --unsafe-fixes . && ruff format .

# Check lint/format without modifying files
lint:
    ruff check . && ruff format --check .

# Open app URL
open-app:
    python -m webbrowser http://localhost:{{port}}
