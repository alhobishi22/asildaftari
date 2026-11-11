import os
from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.api import create_app
from backend.models import Base, User


@pytest.fixture()
def app():
    url = os.getenv('TEST_DATABASE_URL', 'postgresql+psycopg:///daftari_test')
    assert url.endswith('daftari_test'), 'Tests require dedicated daftari_test database'
    app = create_app(url, 'test-only-signing-key-at-least-32-characters')
    Base.metadata.drop_all(app.state.engine)
    with TestClient(app) as client:
        yield app, client
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


def signup(c, name='one'):
    response = c.post('/api/auth/signup', json={'email': f'{name}@example.com', 'password': 'local-test-password', 'displayName': name})
    assert response.status_code == 200, response.text
    return response


def test_auth_errors_cookie_bearer_and_reset(app):
    application, c = app
    assert c.get('/api/clients').status_code == 401
    response = signup(c)
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    token = c.cookies.get('daftari_session')
    c.cookies.clear()
    assert c.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token}).json()['displayName'] == 'one'
    assert c.post('/api/auth/login', json={'email': 'one@example.com', 'password': 'wrong'}).status_code == 401
    assert c.post('/api/auth/login', json={'email': 'one@example.com', 'password': 'local-test-password'}).status_code == 200
    assert c.post('/api/auth/signup', json={'email': 'one@example.com', 'password': 'local-test-password'}).status_code == 409
    assert c.post('/api/auth/reset', json={'email': 'missing@example.com'}).json()['ok']
    assert c.post('/api/auth/google', json={'credential': 'bad'}).status_code == 400
    assert c.post('/api/clients', headers={'Origin': 'https://evil.example'}, json={'name': 'x'}).status_code == 403


def test_crud_isolation_idempotency_archive_void_and_cascade(app):
    application, a = app
    signup(a)
    with TestClient(application) as b:
        signup(b, 'two')
        client_id = str(uuid4())
        one = a.post('/api/clients', json={'id': client_id, 'name': 'محمد', 'userId': 'injected', 'currency': 'USD'}).json()
        assert a.post('/api/clients', json={'id': client_id, 'name': 'duplicate'}).json()['name'] == 'محمد'
        assert b.get('/api/clients').json() == []
        assert b.get(f'/api/clients/{client_id}').status_code == 404
        assert b.put(f'/api/clients/{client_id}', json={'name': 'bad'}).status_code == 404
        assert b.delete(f'/api/clients/{client_id}').status_code == 404
        assert b.post('/api/records', json={'clientId': client_id, 'amount': 20, 'currency': 'USDT'}).status_code == 404
        record = a.post('/api/records', json={'clientId': client_id, 'amount': 20, 'currency': 'USDT', 'type': 'debt', 'date': '2026-02-01'}).json()
        assert record['netAmount'] == 21
        assert a.get('/api/aggregates').json()['usd'] == 21
        assert b.get('/api/records').json() == []
        assert b.get('/api/aggregates').json()['usd'] == 0
        assert b.get(f'/api/clients/{client_id}/statement').status_code == 404
        assert a.post(f'/api/clients/{client_id}/archive').json()['archived']
        assert a.post(f'/api/records/{record["id"]}/void').json()['voided']
        assert a.get('/api/aggregates').json()['usd'] == 0
        assert a.delete(f'/api/clients/{client_id}').status_code == 200
        assert a.get('/api/records').json() == []


def test_settings_lock_overrides_withdrawals_and_backup(app):
    _, c = app
    signup(c)
    client = c.post('/api/clients', json={'name': 'خالد', 'currency': 'SAR', 'rates': {'debt': {'SAR': 4}}}).json()
    record = c.post('/api/records', json={'clientId': client['id'], 'amount': 40, 'currency': 'SAR', 'type': 'debt'}).json()
    assert record['exchangeRate'] == 4 and record['usdEquivalent'] == 10
    config = c.get('/api/settings').json()
    config['rates']['debt']['SAR'] = 5
    assert c.put('/api/settings', json=config).status_code == 200
    assert c.get('/api/records').json()[0]['exchangeRate'] == 4
    withdrawal = c.post('/api/withdrawals', json={'amounts': [100, 200, 0], 'currency': 'YER'}).json()
    assert withdrawal['total'] == 300 and withdrawal['count'] == 2
    assert c.get('/api/aggregates').json()['usd'] == 10
    backup = c.get('/api/backup').json()
    c.put('/api/clients/' + client['id'], json={'name': 'لا تستبدل'})
    assert c.post('/api/restore', json=backup).json()['clients'] == 0
    assert c.get('/api/clients').json()[0]['name'] == 'لا تستبدل'
    c.delete('/api/withdrawals/' + withdrawal['id'])
    assert c.post('/api/restore', json=backup).json()['withdrawals'] == 1
    assert c.post('/api/restore', json={'version': 2}).status_code == 422
    assert c.post('/api/records', json={'clientId': client['id'], 'amount': -1}).status_code == 422
    assert c.post('/api/withdrawals', json={'amounts': []}).status_code == 422
    assert c.post('/api/clients', json={'name': ''}).status_code == 422
    config['rates']['debt']['USD'] = 0
    assert c.put('/api/settings', json=config).status_code == 422


def test_pdf_and_delete_account(app):
    _, c = app
    signup(c)
    client = c.post('/api/clients', json={'name': 'عميل تجريبي'}).json()
    c.post('/api/records', json={'clientId': client['id'], 'amount': 10, 'date': '2026-01-01'})
    for route in ['/api/reports/pdf', f'/api/clients/{client["id"]}/statement/pdf?start=2026-01-01']:
        response = c.get(route)
        assert response.status_code == 200
        assert response.content.startswith(b'%PDF-')
    assert c.request('DELETE', '/api/auth/account', json={}).status_code == 422
    assert c.request('DELETE', '/api/auth/account', json={'confirm': 'حذف'}).status_code == 200
    assert c.get('/api/auth/me').status_code == 401
