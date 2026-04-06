#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 "$(pwd)/relay_webhook.py" >> "$(pwd)/nohup.out" 2>&1
