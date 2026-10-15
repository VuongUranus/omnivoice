#!/usr/bin/env bash
# Khởi chạy OmniVoice Studio (React + Tailwind) — build frontend rồi chạy API tại http://127.0.0.1:8000
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
if [ ! -d "$SCRIPT_DIR/web/dist" ]; then
  (cd "$SCRIPT_DIR/web" && npm install && npm run build)
fi
python "$SCRIPT_DIR/api_server.py" --ip 127.0.0.1 --port 8000 --device mps
