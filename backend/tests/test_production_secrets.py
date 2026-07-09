"""A production instance must not boot on the credentials published in the repo."""
import pytest

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "DEBUG": False,
        "SECRET_KEY": "a-real-secret",
        "SUPER_ADMIN_PASSWORD": "a-real-password",
        "DATABASE_URL": "sqlite:///:memory:",
    }
    return Settings(**{**base, **overrides})


def test_production_rejects_the_default_secret_key():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _settings(SECRET_KEY="insecure-dev-secret-key")


def test_production_rejects_the_default_admin_password():
    """Migration 0003 re-seeds the superadmin from this value on every upgrade,
    so a default left in place is a working admin login for anyone."""
    with pytest.raises(ValueError, match="SUPER_ADMIN_PASSWORD"):
        _settings(SUPER_ADMIN_PASSWORD="Admin123!")


def test_production_accepts_real_credentials():
    s = _settings()
    assert s.SECRET_KEY == "a-real-secret"


def test_development_only_warns(caplog):
    s = Settings(DEBUG=True, SECRET_KEY="insecure-dev-secret-key",
                 SUPER_ADMIN_PASSWORD="Admin123!", DATABASE_URL="sqlite:///:memory:")
    assert s.DEBUG
    assert any("SECRET_KEY" in r.message for r in caplog.records)
    assert any("SUPER_ADMIN_PASSWORD" in r.message for r in caplog.records)
