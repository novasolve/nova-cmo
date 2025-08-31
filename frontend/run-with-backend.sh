#!/bin/bash

# CMO Agent Chat Console - Full Stack Runner
# This script starts both the backend and frontend

echo "🚀 Starting CMO Agent Chat Console with Real Backend..."

# Check if we're in the frontend directory
if [ ! -f "package.json" ]; then
    echo "❌ Please run this script from the frontend directory"
    exit 1
fi

# Create environment file if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "⚙️  Creating environment file..."
    cp env.example .env.local
    echo "✅ Created .env.local"
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Function to check if backend is running
check_backend() {
    curl -s http://localhost:8000/api/jobs >/dev/null 2>&1
    return $?
}

# Check if backend is already running
if check_backend; then
    echo "✅ Backend is already running on port 8000"
else
    echo "🔧 Starting CMO Agent backend..."
    
    # Start backend in background
    (
        cd ../cmo_agent
        if [ -f ".env" ]; then
            source .env
        fi
        python scripts/run_web.py
    ) &
    
    BACKEND_PID=$!
    echo "🔄 Backend started with PID $BACKEND_PID"
    
    # Wait for backend to be ready
    echo "⏳ Waiting for backend to start..."
    for i in {1..30}; do
        if check_backend; then
            echo "✅ Backend is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Backend failed to start after 30 seconds"
            kill $BACKEND_PID 2>/dev/null
            exit 1
        fi
        sleep 1
    done
fi

echo "🎨 Starting frontend development server..."
npm run dev
