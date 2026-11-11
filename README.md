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

Requirements: Python 3.10+, Node 20+, PostgreSQL, and the native Pango/HarfBuzz libraries needed by WeasyPrint.

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
.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
```

Backend integration tests recreate tables **only in the dedicated `daftari_test` database**. Never point `TEST_DATABASE_URL` at an application database. Tests cover tenant isolation, auth, financial formulas, merge restore, statements, PDFs and deletion. Frontend tests cover calculation previews and outbox replay/acknowledgment races.

## Configuration and behavior

- `.env` supplies `DATABASE_URL`, `JWT_SECRET`, `COOKIE_SECURE`, `GOOGLE_CLIENT_ID`, and optional SMTP variables. Set `COOKIE_SECURE=true` behind HTTPS. Google sign-in is hidden unless configured. Password reset currently returns a success response but does not send mail.
- Passwords use bcrypt. Authentication uses a same-site httpOnly JWT cookie; Bearer JWTs are also accepted. Tenant-owned primary/foreign keys include `user_id`.
- Exchange rates and commissions are fixed at entry; the API independently computes persisted monetary fields. Automatic commissions apply only to USDT, including the documented legacy fixed-fee fallback. The documented blank-start-date statement edge is retained.
- Records and withdrawals can be created/edited offline. Each account has its own localStorage cache and durable outbox, capped at 300 distinct rows. Reconnection and periodic retry replay the outbox using stable UUIDs. Rejected rows remain visible and can be edited or explicitly retried from Settings. Clients, settings, backups and server PDFs require connectivity.
- The PWA service worker caches only the application shell/assets/fonts, never API responses. Browser print uses a separate Arabic printable report and works from locally cached data offline.
- Logging out removes the offline identity but preserves that account's pending work for the next login. Shared-device users should log out; locally cached financial data is not encrypted.
- Backup restore is additive: existing rows/settings are kept and only missing IDs are inserted. Existing transaction rates/commissions are preserved. PDFs use bundled open-license Arabic fonts.

`compare/`, `.env`, build output and local caches are deliberately excluded from git. See the local `compare/REPORT.md` for screenshot pairs and end-to-end evidence.
