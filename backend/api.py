import os
import re
from copy import deepcopy
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

import bcrypt
import jwt
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Base, User, Client, Record, Withdrawal, Settings, serialize, camel
from .logic import DEFAULTS, calculate, automatic_commission, exchange_rate, aggregate, statement, number, rounded

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
COLLECTIONS = {'clients': Client, 'records': Record, 'withdrawals': Withdrawal}


def create_app(database_url=None, secret=None):
    engine = create_engine(database_url or os.environ.get('DATABASE_URL', 'postgresql+psycopg:///daftari'), pool_pre_ping=True)
    secret = secret or os.environ.get('JWT_SECRET')
    if not secret or len(secret) < 32:
        raise RuntimeError('JWT_SECRET must contain at least 32 characters')

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        yield

    app = FastAPI(title='دفتري', lifespan=lifespan)
    app.state.engine = engine

    @app.middleware('http')
    async def safeguards(request, call_next):
        if request.url.path.startswith('/api/') and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': 'الطلب غير مسموح'}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    def db():
        with Session(engine) as session:
            yield session

    def current(request: Request, session: Session = Depends(db)):
        authorization = request.headers.get('authorization', '')
        token = authorization[7:] if authorization.lower().startswith('bearer ') else request.cookies.get('daftari_session')
        try:
            payload = jwt.decode(token or '', secret, algorithms=['HS256'], options={'require': ['exp', 'sub']})
            user = session.get(User, payload['sub'])
        except jwt.PyJWTError:
            user = None
        if not user:
            raise HTTPException(401, 'يرجى تسجيل الدخول')
        return user

    def login_cookie(response, user):
        token = jwt.encode({'sub': user.id, 'iat': datetime.now(timezone.utc), 'exp': datetime.now(timezone.utc) + timedelta(days=7)}, secret, algorithm='HS256')
        response.set_cookie('daftari_session', token, httponly=True, samesite='lax', secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', max_age=604800, path='/')

    def config(session, user):
        row = session.get(Settings, (user.id, 'main'))
        if not row:
            row = Settings(user_id=user.id, id='main', **mapped(Settings, deepcopy(DEFAULTS)))
            session.add(row)
            session.commit()
        return row

    def owned(session, model, user, row_id):
        row = session.get(model, (user.id, row_id))
        if not row:
            raise HTTPException(404, 'العنصر غير موجود')
        return row

    def rows(session, model, user):
        return [serialize(row) for row in session.scalars(select(model).where(model.user_id == user.id))]

    @app.get('/api/auth/config')
    def auth_config():
        return {'googleClientId': os.getenv('GOOGLE_CLIENT_ID', '')}

    @app.post('/api/auth/signup')
    def signup(response: Response, body: dict = Body(...), session: Session = Depends(db)):
        email, password = credentials(body)
        if len(password) < 6:
            raise HTTPException(422, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        user = User(email=email, password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), display_name=str(body.get('displayName') or email.split('@')[0])[:200])
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, 'البريد الإلكتروني مستخدم بالفعل')
        config(session, user)
        login_cookie(response, user)
        return serialize(user)

    @app.post('/api/auth/login')
    def login(response: Response, body: dict = Body(...), session: Session = Depends(db)):
        email, password = credentials(body)
        user = session.scalar(select(User).where(User.email == email))
        if not user or not user.password_hash or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            raise HTTPException(401, 'البريد الإلكتروني أو كلمة المرور غير صحيحة')
        login_cookie(response, user)
        return serialize(user)

    @app.post('/api/auth/google')
    def google(response: Response, body: dict = Body(...), session: Session = Depends(db)):
        audience = os.getenv('GOOGLE_CLIENT_ID')
        if not audience:
            raise HTTPException(400, 'تسجيل الدخول عبر Google غير مفعّل')
        from google.oauth2 import id_token
        from google.auth.transport.requests import Request as GoogleRequest
        try:
            info = id_token.verify_oauth2_token(str(body.get('credential', '')), GoogleRequest(), audience)
            if not info.get('email_verified') or not info.get('sub'):
                raise ValueError()
        except (ValueError, Exception) as exc:
            raise HTTPException(401, 'تعذّر التحقق من حساب Google') from exc
        email = info['email'].lower()
        user = session.scalar(select(User).where(User.google_sub == info['sub']))
        if not user:
            user = session.scalar(select(User).where(User.email == email))
            if user and user.google_sub and user.google_sub != info['sub']:
                raise HTTPException(409, 'الحساب مرتبط بمعرّف آخر')
            if not user:
                user = User(email=email, display_name=info.get('name', email.split('@')[0])[:200])
                session.add(user)
            user.google_sub = info['sub']
            session.commit()
        config(session, user)
        login_cookie(response, user)
        return serialize(user)

    @app.post('/api/auth/reset')
    def reset(body: dict = Body(...)):
        return {'ok': True, 'message': 'إذا كان البريد مسجّلًا فستصلك رسالة لاستعادة كلمة المرور.'}

    @app.post('/api/auth/logout')
    def logout(response: Response):
        response.delete_cookie('daftari_session', path='/')
        return {'ok': True}

    @app.get('/api/auth/me')
    def me(user=Depends(current)):
        return serialize(user)

    @app.delete('/api/auth/account')
    def delete_account(response: Response, body: dict = Body(...), user=Depends(current), session: Session = Depends(db)):
        if body.get('confirm') != 'حذف':
            raise HTTPException(422, 'اكتب حذف للتأكيد')
        session.delete(user)
        session.commit()
        response.delete_cookie('daftari_session', path='/')
        return {'ok': True}

    @app.get('/api/settings')
    def get_settings(user=Depends(current), session: Session = Depends(db)):
        return serialize(config(session, user))

    @app.put('/api/settings')
    def put_settings(body: dict = Body(...), user=Depends(current), session: Session = Depends(db)):
        row = config(session, user)
        clean = validate_settings(body)
        for key, value in mapped(Settings, clean).items():
            setattr(row, key, value)
        session.commit()
        return serialize(row)

    def prepare(collection, body, session, user):
        settings = serialize(config(session, user))
        codes = [c['code'] for c in settings['currencies']]
        currency = str(body.get('currency', 'USD')).upper()
        if currency not in codes:
            raise ValueError('العملة غير موجودة في إعدادات الدفتر')
        if collection == 'clients':
            name = str(body.get('name', '')).strip()
            if not name or len(name) > 200:
                raise ValueError('أدخل اسم العميل')
            return {'name': name, 'phone': str(body.get('phone', ''))[:50], 'note': str(body.get('note', ''))[:5000], 'currency': currency, 'archived': bool(body.get('archived', False)), 'rates': numeric_tree(body.get('rates', {})), 'commissions': numeric_tree(body.get('commissions', {}))}
        day = str(body.get('date', date.today().isoformat()))
        date.fromisoformat(day)
        clock = str(body.get('time') or datetime.now().strftime('%H:%M'))
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', clock):
            raise ValueError('الوقت غير صالح')
        common = {'currency': currency, 'date': day, 'time': clock, 'note': str(body.get('note', ''))[:5000], 'createdName': str(body.get('createdName', user.display_name))[:200], 'voided': bool(body.get('voided', False))}
        if collection == 'withdrawals':
            amounts = [number(v) for v in body.get('amounts', []) if number(v) > 0]
            if not amounts or len(amounts) > 1000:
                raise ValueError('أدخل مبلغًا واحدًا على الأقل')
            return {**common, 'amounts': amounts, 'count': len(amounts), 'total': rounded(sum(amounts))}
        client_id = str(body.get('clientId', ''))
        client = serialize(owned(session, Client, user, client_id))
        kind = body.get('type', 'debt')
        if kind not in ['debt', 'payment']:
            raise ValueError('نوع العملية غير صالح')
        rate = number(body.get('exchangeRate'), exchange_rate(settings, client, kind, currency))
        if rate <= 0:
            raise ValueError('سعر الصرف يجب أن يكون أكبر من صفر')
        commission_type = body.get('commissionType', 'auto')
        commission = automatic_commission(settings, client, kind, currency, body.get('amount'), rate) if commission_type == 'auto' else {'commissionType': commission_type, 'commissionValue': body.get('commissionValue', 0)}
        return {**common, 'clientId': client_id, 'type': kind, **calculate(kind, body.get('amount'), currency, rate, commission['commissionType'], commission['commissionValue'])}

    def model_for(collection):
        if collection not in COLLECTIONS:
            raise HTTPException(404)
        return COLLECTIONS[collection]

    @app.get('/api/aggregates')
    def aggregates(user=Depends(current), session: Session = Depends(db)):
        return aggregate(rows(session, Record, user))

    @app.get('/api/clients/{client_id}/statement')
    def get_statement(client_id: str, start: str = '', end: str = '', currency: str = 'ALL', user=Depends(current), session: Session = Depends(db)):
        client = owned(session, Client, user, client_id)
        records = [r for r in rows(session, Record, user) if r['clientId'] == client_id]
        return {'client': serialize(client), **statement(records, start, end, currency)}

    @app.get('/api/backup')
    def backup(user=Depends(current), session: Session = Depends(db)):
        return {'version': 1, 'exportedAt': datetime.now(timezone.utc).isoformat(), 'settings': serialize(config(session, user)), **{coll: rows(session, model, user) for coll, model in COLLECTIONS.items()}}

    @app.post('/api/restore')
    def restore(body: dict = Body(...), user=Depends(current), session: Session = Depends(db)):
        if body.get('version') != 1 or any(not isinstance(body.get(k, []), list) for k in COLLECTIONS):
            raise ValueError('ملف النسخة الاحتياطية غير صالح')
        if sum(len(body.get(k, [])) for k in COLLECTIONS) > 50000:
            raise ValueError('الملف كبير جدًا')
        counts = {key: 0 for key in COLLECTIONS}
        try:
            for coll, model in COLLECTIONS.items():
                for item in body.get(coll, []):
                    row_id = valid_id(item.get('id'))
                    if session.get(model, (user.id, row_id)):
                        continue
                    clean = prepare(coll, item, session, user)
                    session.add(model(user_id=user.id, id=row_id, **mapped(model, clean)))
                    session.flush()
                    counts[coll] += 1
            if not session.get(Settings, (user.id, 'main')) and body.get('settings'):
                session.add(Settings(user_id=user.id, id='main', **mapped(Settings, validate_settings(body['settings']))))
            session.commit()
        except Exception:
            session.rollback()
            raise
        return {'ok': True, **counts}

    @app.get('/api/reports/pdf')
    def report_pdf(user=Depends(current), session: Session = Depends(db)):
        from .pdf import report
        content = report(serialize(config(session, user)), rows(session, Client, user), aggregate(rows(session, Record, user)))
        return Response(content, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="daftari-report.pdf"'})

    @app.get('/api/clients/{client_id}/statement/pdf')
    def statement_pdf(client_id: str, start: str = '', end: str = '', currency: str = 'ALL', user=Depends(current), session: Session = Depends(db)):
        from .pdf import client_statement
        client = serialize(owned(session, Client, user, client_id))
        data = statement([r for r in rows(session, Record, user) if r['clientId'] == client_id], start, end, currency)
        content = client_statement(serialize(config(session, user)), client, data, start, end, currency)
        return Response(content, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="statement.pdf"'})

    @app.get('/api/{collection}')
    def list_rows(collection: str, user=Depends(current), session: Session = Depends(db)):
        return rows(session, model_for(collection), user)

    @app.get('/api/{collection}/{row_id}')
    def get_row(collection: str, row_id: str, user=Depends(current), session: Session = Depends(db)):
        return serialize(owned(session, model_for(collection), user, row_id))

    @app.post('/api/{collection}', status_code=201)
    def insert(collection: str, body: dict = Body(...), user=Depends(current), session: Session = Depends(db)):
        model = model_for(collection)
        row_id = valid_id(body.get('id') or str(uuid4()))
        existing = session.get(model, (user.id, row_id))
        if existing:
            return serialize(existing)
        clean = prepare(collection, body, session, user)
        row = model(user_id=user.id, id=row_id, **mapped(model, clean))
        session.add(row)
        session.commit()
        return serialize(row)

    @app.put('/api/{collection}/{row_id}')
    def update(collection: str, row_id: str, body: dict = Body(...), user=Depends(current), session: Session = Depends(db)):
        model = model_for(collection)
        row = owned(session, model, user, row_id)
        clean = prepare(collection, {**serialize(row), **body}, session, user)
        for key, value in mapped(model, clean).items():
            setattr(row, key, value)
        session.commit()
        return serialize(row)

    @app.post('/api/{collection}/{row_id}/{action}')
    def toggle(collection: str, row_id: str, action: str, body: dict = Body(default={}), user=Depends(current), session: Session = Depends(db)):
        model = model_for(collection)
        row = owned(session, model, user, row_id)
        field = 'archived' if collection == 'clients' and action == 'archive' else 'voided' if collection in ['records', 'withdrawals'] and action == 'void' else None
        if not field:
            raise HTTPException(404)
        setattr(row, field, bool(body.get(field, not getattr(row, field))))
        session.commit()
        return serialize(row)

    @app.delete('/api/{collection}/{row_id}')
    def remove(collection: str, row_id: str, user=Depends(current), session: Session = Depends(db)):
        session.delete(owned(session, model_for(collection), user, row_id))
        session.commit()
        return {'ok': True}

    dist = ROOT / 'frontend' / 'dist'
    if (dist / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def spa(path: str):
        if path.startswith('api/'):
            raise HTTPException(404)
        candidate = (dist / path).resolve()
        if candidate.is_relative_to(dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        if (dist / 'index.html').exists():
            return FileResponse(dist / 'index.html', headers={'Cache-Control': 'no-cache'})
        raise HTTPException(503, 'Build frontend first')
    return app


def mapped(model, body):
    return {col.name: body[camel(col.name)] for col in model.__table__.columns if col.name not in ['user_id', 'id', 'created_at', 'updated_at'] and camel(col.name) in body}


def credentials(body):
    try:
        email = validate_email(str(body.get('email', '')).strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise HTTPException(422, 'أدخل بريدًا إلكترونيًا صالحًا')
    password = str(body.get('password', ''))
    if not password or len(password.encode()) > 72:
        raise HTTPException(422, 'كلمة المرور مطلوبة ولا تتجاوز 72 بايت')
    return email, password


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise ValueError('معرّف غير صالح')
    return value


def numeric_tree(value):
    if not isinstance(value, dict):
        raise ValueError('بيانات غير صالحة')
    return {str(k): numeric_tree(v) if isinstance(v, dict) else number(v) for k, v in value.items() if v is not None and v != ''}


def validate_settings(body):
    data = {**deepcopy(DEFAULTS), **body}
    currencies = data['currencies']
    if not isinstance(currencies, list) or not currencies or len(currencies) > 40:
        raise ValueError('أضف عملة واحدة على الأقل')
    codes = [c.get('code', '') for c in currencies]
    if len(set(codes)) != len(codes) or any(not re.fullmatch(r'[A-Z0-9]{2,12}', c) for c in codes):
        raise ValueError('رموز العملات غير صالحة أو مكرّرة')
    data['currencies'] = [{'code': c['code'], 'name': str(c.get('name', c['code']))[:100], 'symbol': str(c.get('symbol', c['code']))[:20]} for c in currencies]
    data['rates'] = numeric_tree(data['rates'])
    for kind in ['debt', 'payment']:
        if any(number(data['rates'].get(kind, {}).get(code)) <= 0 for code in codes):
            raise ValueError('أسعار الصرف يجب أن تكون أكبر من صفر')
        rule = data['commissions'][kind]
        for key in ['smallUsd', 'threshold', 'percent', 'fixed']:
            rule[key] = max(0, number(rule.get(key), DEFAULTS['commissions'][kind][key]))
        rule['byCurrency'] = numeric_tree(rule.get('byCurrency', {}))
        rule['mode'], rule['currencies'] = 'tiered', ['USDT']
    data['shopName'] = str(data.get('shopName', 'دفتري'))[:200]
    data['shopPhone'] = str(data.get('shopPhone', ''))[:50]
    return data
