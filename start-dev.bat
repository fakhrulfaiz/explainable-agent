@echo off

REM Start development environment for Explainable Agent

echo 🚀 Starting Explainable Agent Development Environment...

REM Check if .env files exist
if not exist "backend\.env" (
    echo ⚠️  Backend .env file not found!
    echo Please create backend\.env file using the template in README-Docker.md
    exit /b 1
)

if not exist "frontend\.env" (
    echo ⚠️  Frontend .env file not found!
    echo Please create frontend\.env file using the template in README-Docker.md
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker first.
    exit /b 1
)

echo 📦 Building and starting containers...

REM Start with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

REM Check if the command was successful
if %errorlevel% equ 0 (
    echo.
    echo ✅ Development environment started successfully!
    echo.
    echo 🌐 Application: http://localhost
    echo 🔗 Backend API: http://localhost/api
    echo 📚 API Docs: http://localhost/docs
    echo 🏥 Health Check: http://localhost/health
    echo.
    echo 📋 Direct service access (for debugging):
    echo   Frontend: http://localhost:5173
    echo   Backend: http://localhost:8000
    echo.
    echo To stop: Ctrl+C or run 'docker-compose down'
) else (
    echo.
    echo ❌ Failed to start development environment!
    echo.
    echo Common issues:
    echo - Port 5173 or 8000 already in use
    echo - Missing .env files
    echo - Docker not running
    echo.
    echo To check what's using the ports:
    echo   netstat -ano ^| findstr :5173
    echo   netstat -ano ^| findstr :8000
    echo.
    echo To stop any existing containers:
    echo   docker-compose down
    exit /b 1
)
