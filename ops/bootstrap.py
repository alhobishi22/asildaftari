"""Initialize or update only the isolated /opt/daftari service."""
import os
from pathlib import Path
import pwd
import secrets
import subprocess

ROOT = Path('/opt/daftari')
ENV = ROOT / '.env'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def sql(statement):
    return run('runuser', '-u', 'postgres', '--', 'psql', '-XAt', '-v', 'ON_ERROR_STOP=1',
               input=statement, capture_output=True).stdout.strip()


if os.geteuid() != 0 or not ROOT.is_dir():
    raise SystemExit('Run as root only after uploading to /opt/daftari')

if not ENV.exists():
    conflicts = sql("SELECT 'database' FROM pg_database WHERE datname='daftari' UNION ALL "
                    "SELECT 'role' FROM pg_roles WHERE rolname='daftari';")
    if conflicts:
        raise SystemExit('Refusing to reuse existing database/role without a daftari .env: ' + conflicts)

run('apt-get', 'update', '-qq')
run('apt-get', 'install', '-y', '--no-install-recommends', 'python3-venv', 'libpango-1.0-0',
    'libpangoft2-1.0-0', 'libharfbuzz-subset0', 'libgdk-pixbuf-2.0-0', 'libffi8', 'shared-mime-info')
try:
    account = pwd.getpwnam('daftari')
except KeyError:
    run('useradd', '--system', '--user-group', '--home-dir', str(ROOT), '--shell', '/usr/sbin/nologin', 'daftari')
    account = pwd.getpwnam('daftari')

if not ENV.exists():
    password = secrets.token_hex(32)
    sql(f"CREATE ROLE daftari LOGIN PASSWORD '{password}';\nCREATE DATABASE daftari OWNER daftari;")
    settings = (f'DATABASE_URL=postgresql+psycopg://daftari:{password}@127.0.0.1:5432/daftari\n'
                f'JWT_SECRET={secrets.token_hex(48)}\nCOOKIE_SECURE=false\nGOOGLE_CLIENT_ID=\n')
    descriptor = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write(settings)
    os.chown(ENV, account.pw_uid, account.pw_gid)

os.chmod(ENV, 0o600)
if not (ROOT / '.venv/bin/python').exists():
    run('python3', '-m', 'venv', str(ROOT / '.venv'))
run(str(ROOT / '.venv/bin/pip'), 'install', '--disable-pip-version-check', '-r', str(ROOT / 'backend/requirements.txt'))
run('install', '-m', '644', str(ROOT / 'ops/daftari.service'), '/etc/systemd/system/daftari.service')
run('systemctl', 'daemon-reload')
run('systemctl', 'enable', 'daftari')
run('systemctl', 'restart', 'daftari')
run('ufw', 'allow', '8097/tcp', 'comment', 'daftari')
run('systemctl', 'is-active', 'daftari')
print('DAFTARI_BOOTSTRAP_OK env_mode=600 port=8097')
