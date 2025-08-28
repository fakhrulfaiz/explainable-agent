#!/bin/bash

# Start development environment for Explainable Agent

echo "🚀 Starting Explainable Agent Development Environment..."

# Check if .env files exist
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Backend .env file not found!"
    echo "Please create backend/.env file using the template in README-Docker.md"
    exit 1
fi

if [ ! -f "frontend/.env" ]; then
    echo "⚠️  Frontend .env file not found!"
    echo "Please create frontend/.env file using the template in README-Docker.md"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "📦 Building and starting containers..."

# Start with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

echo "✅ Development environment started!"
echo ""
echo "🌐 Frontend: http://localhost:5173"
echo "🔗 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "To stop: Ctrl+C or run 'docker-compose down'"
