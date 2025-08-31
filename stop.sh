#!/bin/bash

echo "🛑 Stopping CMO Agent services..."

# Kill backend (port 8000)
BACKEND_PIDS=$(lsof -ti:8000 2>/dev/null)
if [ ! -z "$BACKEND_PIDS" ]; then
    echo "🔴 Stopping backend (port 8000)..."
    echo "$BACKEND_PIDS" | xargs kill -TERM 2>/dev/null
    sleep 2
    # Force kill if still running
    REMAINING=$(lsof -ti:8000 2>/dev/null)
    if [ ! -z "$REMAINING" ]; then
        echo "🔥 Force killing backend..."
        echo "$REMAINING" | xargs kill -9 2>/dev/null
    fi
    echo "✅ Backend stopped"
else
    echo "ℹ️  Backend not running"
fi

# Kill frontend (port 3000 or 3001)
for PORT in 3000 3001; do
    FRONTEND_PIDS=$(lsof -ti:$PORT 2>/dev/null)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        echo "🔴 Stopping frontend (port $PORT)..."
        echo "$FRONTEND_PIDS" | xargs kill -TERM 2>/dev/null
        sleep 1
        # Force kill if still running
        REMAINING=$(lsof -ti:$PORT 2>/dev/null)
        if [ ! -z "$REMAINING" ]; then
            echo "🔥 Force killing frontend..."
            echo "$REMAINING" | xargs kill -9 2>/dev/null
        fi
        echo "✅ Frontend stopped (port $PORT)"
    fi
done

echo "🏁 All services stopped"
