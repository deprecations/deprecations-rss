set shell := ["bash", "-cu"]
port := env_var_or_default("PORT", "8910")

up:
    uv sync

run:
    uv run python -m src.main

server:
    cd docs && python -m http.server {{port}}

test:
    uv run pytest .

format:
    uv run ruff check --fix --unsafe-fixes . && uv run ruff format .

lint:
    uv run ruff check . && uv run ruff format --check .

open:
    python -m webbrowser http://localhost:{{port}}
