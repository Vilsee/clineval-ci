#!/usr/bin/env bash
# Runs ON the Azure VM (invoked over SSH by Jenkins after rsync).
set -euo pipefail
cd /opt/clineval
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
sudo systemctl restart clineval
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then
    echo "Service healthy after restart"; exit 0
  fi
  sleep 2
done
echo "Service failed health check" >&2
sudo journalctl -u clineval -n 30 --no-pager >&2
exit 1
