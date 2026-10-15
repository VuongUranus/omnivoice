#!/usr/bin/env bash
# Script khởi chạy giao diện Web UI cục bộ của OmniVoice trên Apple Silicon (MPS)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"

echo "========================================================"
echo " Đang khởi động OmniVoice Web UI trên Mac (MPS)..."
echo " Truy cập giao diện tại: http://127.0.0.1:7860"
echo "========================================================"

python "$SCRIPT_DIR/app_omnivoice.py" --ip 127.0.0.1 --port 7860 --device mps
