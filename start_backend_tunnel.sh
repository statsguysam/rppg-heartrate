#!/bin/bash
# Starts backend + exposes it via ngrok for phone testing
# Run: bash start_backend_tunnel.sh

export PATH="/opt/homebrew/bin:$PATH"
SCRIPT_DIR="$(dirname "$0")"

echo ""
echo "======================================"
echo "  rPPG Backend + ngrok tunnel"
echo "======================================"
echo ""

# 1. Start backend in background
echo "▶ Starting FastAPI backend on port 8000..."
cd "$SCRIPT_DIR/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"
sleep 3

# 2. Start ngrok tunnel
echo ""
echo "▶ Starting ngrok tunnel..."
echo "  → Copy the https:// URL ngrok shows below"
echo "  → Paste it into mobile/.env as EXPO_PUBLIC_BACKEND_URL"
echo "  → Then rebuild: cd mobile && eas build --platform android --profile production"
echo ""
ngrok http 8000

# Cleanup on exit
kill $BACKEND_PID 2>/dev/null
