#!/usr/bin/env bash
# Khởi chạy OmniVoice Studio (React + Tailwind): build lại frontend mỗi lần rồi chạy API tại http://127.0.0.1:8000
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"

cd "$SCRIPT_DIR/web"
[ -d node_modules ] || npm install
npm run build

cd "$SCRIPT_DIR"
python "$SCRIPT_DIR/api_server.py" --ip 127.0.0.1 --port 8000 --device mps
