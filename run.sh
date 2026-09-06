#!/usr/bin/env bash
# Gunluk tarama baslatici. cron/systemd bunu cagirir.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
exec python -m bist_screener.daily "$@"
