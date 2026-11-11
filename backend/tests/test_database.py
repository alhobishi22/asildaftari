import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import NullPool

from backend.database import database_url, make_engine


@pytest.mark.parametrize('prefix', ['postgres://', 'postgresql://', 'postgresql+psycopg://'])
def test_neon_url_preserves_ssl_and_credentials(prefix):
    normalized = database_url(prefix + 'user:p%40ss@localhost/db?sslmode=require&channel_binding=require')
    url = make_url(normalized)
    assert url.drivername == 'postgresql+psycopg'
    assert url.password == 'p@ss'
    assert url.query == {'sslmode': 'require', 'channel_binding': 'require'}


def test_default_and_non_postgres_urls():
    assert database_url('sqlite://') == 'sqlite://'
    with pytest.raises(ArgumentError):
        make_engine('not-a-database-url')


@pytest.mark.parametrize('environment', [{'VERCEL': '1'}, {'DB_POOL': 'null'}])
def test_serverless_disables_connection_pool(monkeypatch, environment):
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    engine = make_engine('postgres://localhost/unused?sslmode=require')
    assert isinstance(engine.pool, NullPool)
    assert engine.url.query['sslmode'] == 'require'
    engine.dispose()
