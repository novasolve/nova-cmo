#!/bin/bash

# CMO Agent Chat Console - Quick Start Script

echo "🚀 Starting CMO Agent Chat Console..."

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Check if .env.local exists, if not create from example
if [ ! -f ".env.local" ]; then
    echo "⚙️  Creating environment file..."
    cp env.example .env.local
    echo "✅ Created .env.local - edit this file to connect to your backend"
fi

echo "🏗️  Building and starting development server..."
npm run dev
