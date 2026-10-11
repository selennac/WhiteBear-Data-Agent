import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.db.connections import DatabaseConfigurationError, parse_url
from app.db.initialize import provisioning_urls


def settings() -> Settings:
    return Settings(
        _env_file=None,
        admin_database_url="postgresql+psycopg://postgres:admin@localhost/postgres",
        app_database_url="postgresql+psycopg://whitebear_app:app@localhost/whitebear_app",
        business_database_url=(
            "postgresql+psycopg://whitebear_business_owner:owner@localhost/whitebear_business"
        ),
        business_readonly_database_url=(
            "postgresql+psycopg://whitebear_business_reader:reader@localhost/whitebear_business"
        ),
    )


def test_provisioning_requires_isolated_roles_databases_and_same_server() -> None:
    config = settings()
    assert provisioning_urls(config)["reader"].database == "whitebear_business"
    config.business_readonly_database_url = config.business_database_url
    with pytest.raises(DatabaseConfigurationError):
        provisioning_urls(config)
    config = settings()
    config.app_database_url = SecretStr(
        "postgresql+psycopg://whitebear_app:app@elsewhere/whitebear_app"
    )
    with pytest.raises(DatabaseConfigurationError):
        provisioning_urls(config)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "not a url",
        "sqlite:///private",
        "postgresql://a:b@host/db",
        "postgresql+psycopg://a:private@host/db?options=unsafe",
    ],
)
def test_bad_connection_strings_never_expose_values(value: str | None) -> None:
    with pytest.raises(DatabaseConfigurationError) as error:
        parse_url(SecretStr(value) if value else None, "TEST_URL")
    assert "private" not in str(error.value)
