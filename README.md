# دفتري

دفتر عملاء عربي مستقل: ديون وتسديدات بعملات متعددة، عمولات USDT، سحوبات مستقلة، كشوف PDF عربية ونسخ احتياطية. لا يتصل بالتطبيق الأصلي أو ببيانات مستخدميه.

## التشغيل والنشر

للتشغيل المحلي: أنشئ قاعدة PostgreSQL باسم `daftari`، ثبّت متطلبات `backend/requirements.txt` في venv، انسخ `.env.example` إلى `.env` واضبط قاعدة البيانات و`JWT_SECRET` العشوائي (32 حرفًا على الأقل). ثم:

```sh
npm --prefix frontend install
npm --prefix frontend run build
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

افتح http://localhost:8080 وأنشئ حسابًا. خطوات إنشاء venv والاختبارات مفصّلة أدناه.

النشر المقصود: http://217.216.111.54:8097/، في `/opt/daftari` بخدمة systemd باسم `daftari`. لا يتغيّر nginx أو أي موقع قائم. بعد حفظ التغييرات في git شغّل `bash deploy.sh` بمفتاح SSH أو `SSHPASS` عبر بيئة آمنة. يُبنى frontend محليًا، ويُرفع آخر commit مع `dist` والخطوط؛ لا يلزم Node أو git على الخادم. أول تشغيل ينشئ مستخدم نظام وقاعدة ودور PostgreSQL مستقلين باسم `daftari`، ويرفض إعادة استخدام قاعدة/دور موجودين دون ملف إعدادات للتطبيق. التحديثات تحفظ `/opt/daftari/.env` كما هو وتعيد تشغيل هذه الخدمة فقط.

كلمة مرور قاعدة البيانات وJWT_SECRET يولَّدان على الخادم ويُحفظان في `.env` بصلاحية 600 فقط. `COOKIE_SECURE=false` مطلوب على HTTP، وزر Google مخفي ما دام `GOOGLE_CLIENT_ID` فارغًا. **عنوان IP عبر HTTP لا يتيح Service Worker/PWA؛ إعادة فتح التطبيق دون شبكة تتطلب HTTPS أو localhost. يُنصح بإضافة نطاق وTLS قبل استخدام بيانات حساسة.** استعادة كلمة المرور واجهة تجريبية بلا إرسال بريد حاليًا. البيانات المحلية غير مشفّرة؛ سجّل الخروج على الأجهزة المشتركة.

ملفات `.env` و`compare/` و`node_modules/` و`dist/` وملفات Python المؤقتة مستثناة من git.

Standalone Arabic RTL client ledger. All financial data belongs to the authenticated local user; this implementation does not contact the original app or its data services.

## Run locally

Requirements: Python 3.10+ (Python 3.12 on Vercel), Node 20+, and PostgreSQL. PDFs use fpdf2 + uharfbuzz wheels and bundled Arabic fonts; no Pango/WeasyPrint system packages are required.

```sh
createdb daftari
createdb daftari_test
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
# Set JWT_SECRET to a random secret (at least 32 characters).
npm --prefix frontend install
npm --prefix frontend run build
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

Open http://localhost:8080 and create a new account. Tables are created on startup. FastAPI serves both `/api` and the compiled SPA. For frontend development, run `npm --prefix frontend run dev` alongside the API; Vite proxies `/api` to port 8080.

## Tests

```sh
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
```

Backend integration tests recreate tables **only in the dedicated `daftari_test` database**. Never point `TEST_DATABASE_URL` at an application database. Tests cover tenant isolation, auth, financial formulas, merge restore, statements, PDFs and deletion. Frontend tests cover calculation previews and outbox replay/acknowledgment races.

## Configuration and behavior

- `.env` supplies `DATABASE_URL`, `JWT_SECRET`, `COOKIE_SECURE`, `GOOGLE_CLIENT_ID`, and optional SMTP variables. HTTPS requests automatically receive Secure cookies; `COOKIE_SECURE=true` can additionally enforce Secure cookies behind a trusted HTTPS proxy. Leave it false for the plain HTTP IP deployment. Google sign-in is hidden unless configured. Password reset currently returns a success response but does not send mail.
- Passwords use bcrypt. Authentication uses a same-site httpOnly JWT cookie; Bearer JWTs are also accepted. Tenant-owned primary/foreign keys include `user_id`.
- Exchange rates and commissions are fixed at entry; the API independently computes persisted monetary fields. Automatic commissions apply only to USDT, including the documented legacy fixed-fee fallback. The documented blank-start-date statement edge is retained.
- Records and withdrawals can be created/edited offline. Each account has its own localStorage cache and durable outbox, capped at 300 distinct rows. Reconnection and periodic retry replay the outbox using stable UUIDs. Rejected rows remain visible and can be edited or explicitly retried from Settings. Clients, settings, backups and server PDFs require connectivity.
- The PWA service worker caches only the application shell/assets/fonts, never API responses. Browser print uses a separate Arabic printable report and works from locally cached data offline.
- Logging out removes the offline identity but preserves that account's pending work for the next login. Shared-device users should log out; locally cached financial data is not encrypted.
- Backup restore is additive: existing rows/settings are kept and only missing IDs are inserted. Existing transaction rates/commissions are preserved. PDFs use bundled open-license Arabic fonts.

`compare/`, `.env`, build output and local caches are deliberately excluded from git. See the local `compare/REPORT.md` for screenshot pairs and end-to-end evidence.

## Vercel (prepared, not deployed)

استورد المستودع وحدّد **Root Directory = جذر المستودع** (وليس frontend). يضبط `vercel.json` بناء Vite، والملفات الثابتة، ودالة Python في `api/index.py` لجميع `/api/*`، ثم SPA fallback لبقية الصفحات. متطلبات Python في `requirements.txt` الجذري؛ الخطوط مضمّنة في الدالة. لا يحتاج PDF إلى حزم نظام.

Use the repository root, Python 3.12, and Node 20+. The checked-in configuration installs/builds the frontend and serves its static output separately from the API function. Do not choose the FastAPI framework preset, which would route the entire site through Python; the configuration explicitly selects Vite. No Vercel deployment has been performed.

Set these project environment variables for each intended environment (Production/Preview/Development):

| Variable | Value / purpose |
| --- | --- |
| `DATABASE_URL` | Required. Neon PostgreSQL URL ending in `?sslmode=require` (preserve any other Neon parameters). `postgres://`, `postgresql://`, and `postgresql+psycopg://` are accepted. Prefer Neon's pooled endpoint. |
| `JWT_SECRET` | Required. Independently generated random secret, at least 32 characters; keep stable across function instances. |
| `DB_POOL` | Set `null` for serverless. `VERCEL=1` (automatically supplied by Vercel) also selects SQLAlchemy NullPool. |
| `GOOGLE_CLIENT_ID` | Optional; leave empty to hide Google sign-in. If enabled, authorize the Vercel domain with Google. |
| `COOKIE_SECURE` | Optional, `true` on Vercel. HTTPS is detected automatically; keep `false` on the existing HTTP IP deployment. |

There are **no `VITE_*` API URL variables**: the frontend uses same-origin `/api`. No SMTP variables are needed: password reset is still a no-mail stub. Vercel supplies `VERCEL` itself. Do not reuse production Neon credentials for disposable preview deployments unless shared data is intentional; use separate Neon branches/databases instead.

Initialize the intended database once from a local shell with its `DATABASE_URL` securely exported (never put credentials in command history):

```sh
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m backend.init_db
```

The command prints `DATABASE_INIT_OK`. Startup also initializes idempotently, with a PostgreSQL transaction advisory lock to serialize concurrent cold starts. The first DB request initializes too when an ASGI adapter does not invoke lifespan. This is additive table creation, not a schema migration system. The Neon role needs table-creation permissions for initialization; all tenant data remains scoped to the signed-in user.

Local function simulation, after building the frontend:

```sh
DB_POOL=null VERCEL=1 .venv/bin/uvicorn api.index:app --host 127.0.0.1 --port 8081
```

This exercises the same ASGI entrypoint and pip-only renderer, but is not a hosted Vercel routing/deployment test. Keep the existing IP service using `backend.main:app` and `deploy.sh`; its environment/database are independent and preserved. Serverless has no durable local disk: app data belongs in PostgreSQL and PDF bytes are generated in memory. Vercel request/runtime/response-size limits still apply to exceptionally large backups or PDFs; use the IP service for exports exceeding the platform's limits.
