import importlib
import os
import sys

import pytest

import app.config


def test_prod_config_default_fallback(monkeypatch):
    """Test that ProdConfig defaults to a local PostgreSQL connection when DATABASE_URL is unset."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Reload the config module to re-evaluate class definitions with the new environment
    importlib.reload(app.config)

    assert app.config.ProdConfig.SQLALCHEMY_DATABASE_URI == (
        "postgresql://postgres:postgres@localhost:5432/adaptive_articulate"
    )


def test_prod_config_postgres_rewrite(monkeypatch):
    """Test that ProdConfig automatically rewrites the legacy postgres:// scheme to postgresql://."""
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/dbname")

    importlib.reload(app.config)

    assert app.config.ProdConfig.SQLALCHEMY_DATABASE_URI == (
        "postgresql://user:pass@host:5432/dbname"
    )


def test_prod_config_postgresql_direct(monkeypatch):
    """Test that ProdConfig preserves postgresql:// schemes directly."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/dbname")

    importlib.reload(app.config)

    assert app.config.ProdConfig.SQLALCHEMY_DATABASE_URI == (
        "postgresql://user:pass@host:5432/dbname"
    )


def test_prod_config_invalid_scheme(monkeypatch):
    """Test that ProdConfig raises a ValueError when a non-Postgres scheme (e.g. SQLite) is provided."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")

    with pytest.raises(ValueError) as excinfo:
        importlib.reload(app.config)

    assert "Production database must use PostgreSQL" in str(excinfo.value)
