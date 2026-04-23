#!/bin/bash
set -e

echo "🚀 Starting Hafen with Docker Compose..."
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install it first:"
    echo "  brew install docker-compose"
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Creating from .env.example..."
    cp .env.example .env
fi

# Start services
echo "📦 Building and starting services..."
echo ""
docker-compose up

echo ""
echo "✅ Hafen is running!"
echo ""
echo "Available at:"
echo "  • Web:  http://localhost:3000"
echo "  • API:  http://localhost:8000"
echo "  • Docs: http://localhost:8000/docs"
echo "  • DB:   localhost:5432 (hafen / hafen_dev_pw)"
echo ""
echo "To stop: Press Ctrl+C or run 'docker-compose down'"
