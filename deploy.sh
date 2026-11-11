#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
target="${DEPLOY_TARGET:-root@217.216.111.54}"
transport='ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15'
if [[ -n "${SSHPASS:-}" ]]; then transport="sshpass -e $transport"; fi
read -r -a remote <<< "$transport"
git diff --quiet && git diff --cached --quiet || { echo 'Commit tracked changes before deploying.' >&2; exit 1; }
npm --prefix frontend run build
"${remote[@]}" "$target" 'test -d /opt && install -d -m 755 /opt/daftari /opt/daftari/frontend/dist'
git archive HEAD backend frontend/public/fonts ops README.md .env.example requirements.txt | "${remote[@]}" "$target" 'tar -xf - -C /opt/daftari'
rsync -az --delete -e "$transport" frontend/dist/ "$target:/opt/daftari/frontend/dist/"
"${remote[@]}" "$target" 'python3 /opt/daftari/ops/bootstrap.py'
curl --fail --silent --show-error --retry 8 --retry-connrefused --retry-delay 2 http://217.216.111.54:8097/ -o /dev/null
printf 'DEPLOY_OK commit=%s url=http://217.216.111.54:8097/\n' "$(git rev-parse HEAD)"
