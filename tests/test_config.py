from app.core.config import Settings


def test_cors_origins_parses_comma_separated_string():
    settings = Settings(cors_origins="http://a:1,http://b:2")
    assert settings.cors_origins == ["http://a:1", "http://b:2"]


def test_cors_origins_default_from_env_is_list():
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:3000"]
    assert isinstance(settings.cors_origins, list)
