#!/bin/bash

echo "🚀 Starting Agentic Demo Frontend..."
echo "📍 Frontend will be available at: http://localhost:3000"
echo "🔧 Admin interface at: http://localhost:3000/admin"
echo "🌐 Demo page at: http://localhost:3000"
echo ""
echo "Make sure the backend is running on http://localhost:8000"
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the development server
npm run dev

