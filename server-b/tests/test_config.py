import importlib
from app import config


def test_allowed_origins_parsing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://a.com, http://b.com")
    importlib.reload(config)
    assert config.settings.allowed_origins == ["http://a.com", "http://b.com"]

    monkeypatch.setenv("ALLOWED_ORIGINS", '["http://c.com", "http://d.com"]')
    importlib.reload(config)
    assert config.settings.allowed_origins == ["http://c.com", "http://d.com"]
