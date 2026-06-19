#!/bin/bash
set -e

echo "Running black..."
venv/bin/black --check app

echo "Running isort..."
venv/bin/isort --check-only app

echo "Running ruff..."
venv/bin/ruff check app

echo "Running mypy..."
venv/bin/mypy app
