#!/usr/bin/env bash
# KaziAI Full Stack Launcher
# Usage: ./start.sh [stop]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

BACKEND_PORT="${PORT:-8030}"
FRONTEND_PORT="${FRONTEND_PORT:-3030}"

stop_all() {
    echo "Stopping KaziAI services..."
    pkill -f "uvicorn src.server" 2>/dev/null || true
    pkill -f "celery -A src.celery_app" 2>/dev/null || true
    pkill -f "vite.*${FRONTEND_PORT}" 2>/dev/null || true
    echo "All services stopped."
}

if [ "${1:-}" = "stop" ]; then
    stop_all
    exit 0
fi

# Check dependencies
command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
command -v redis-cli >/dev/null || { echo "redis-cli not found"; exit 1; }

# Check Redis
redis-cli ping >/dev/null 2>&1 || { echo "Redis not running. Start it first."; exit 1; }

# Check Ollama if using local inference
if [ "${LLM_PROVIDER:-}" = "ollama" ]; then
    curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 || {
        echo "Ollama not running. Starting..."
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    }
fi

# Load env
if [ -f .env ]; then
    set -a; source .env; set +a
fi

# Activate venv if it exists
if [ -d .venv ]; then
    source .venv/bin/activate
fi

echo "Starting KaziAI..."

# Backend
nohup python3 -m uvicorn src.server:app \
    --host "${HOST:-0.0.0.0}" \
    --port "$BACKEND_PORT" \
    --timeout-keep-alive 300 \
    > /tmp/kaziai-backend.log 2>&1 &
echo "  Backend: http://localhost:${BACKEND_PORT}"

# Celery worker + beat
nohup celery -A src.celery_app worker --beat --loglevel=warning \
    > /tmp/kaziai-celery.log 2>&1 &
echo "  Celery: worker + beat scheduler"

# Frontend
cd frontend
nohup npx vite --port "$FRONTEND_PORT" --host \
    > /tmp/kaziai-frontend.log 2>&1 &
cd ..
echo "  Frontend: http://localhost:${FRONTEND_PORT}"

echo ""
echo "KaziAI is running. Use './start.sh stop' to shut down."
