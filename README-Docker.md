# Docker Development Setup

This guide will help you set up the Explainable Agent project using Docker for development.

## Prerequisites

- Docker
- Docker Compose
- Git

## Environment Variables

### Backend Environment Variables

Create a `.env` file in the `backend/` directory with the following variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# DeepSeek Configuration (if using DeepSeek)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Database Configuration
DATABASE_URL=sqlite:///./src/resource/art.db

# Application Settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# LangSmith Configuration (optional)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=explainable-agent
```

### Frontend Environment Variables

Create a `.env` file in the `frontend/` directory with the following variables:

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000

# Development Mode
VITE_DEV_MODE=true

# Application Settings
VITE_APP_NAME=Explainable Agent
VITE_APP_VERSION=1.0.0
```

## Getting Started

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd Explainable-Agent
```

### 2. Create Environment Files

Create the `.env` files in both `backend/` and `frontend/` directories using the templates above.

### 3. Development Mode

For development with hot reload:

```bash
# Start both services
docker-compose up

# Or start with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 4. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Backend Docs**: http://localhost:8000/docs

## Development Workflow

### Hot Reload

Both frontend and backend support hot reload in development mode:

- **Frontend**: Changes to TypeScript/React files will automatically reload the browser
- **Backend**: Changes to Python files will automatically restart the FastAPI server

### Volumes

The setup includes several volumes for development:

- **Source Code**: Bind mounts for live code editing
- **Dependencies**: Named volumes to persist installed packages
- **Logs**: Named volumes for persistent log storage

### Common Commands

```bash
# Stop all services
docker-compose down

# Rebuild services after dependency changes
docker-compose up --build

# Remove all containers and volumes
docker-compose down -v

# Access backend container shell
docker-compose exec backend bash

# Access frontend container shell
docker-compose exec frontend sh

# View running containers
docker-compose ps

# Install new backend dependency
docker-compose exec backend pip install <package-name>
docker-compose exec backend pip freeze > requirements.txt

# Install new frontend dependency
docker-compose exec frontend npm install <package-name>
```

## Troubleshooting

### Port Conflicts

If ports 5173 or 8000 are already in use, modify the port mappings in `docker-compose.yml`:

```yaml
ports:
  - "3000:5173" # Frontend
  - "8080:8000" # Backend
```

### Permission Issues (Linux/Mac)

If you encounter permission issues with volumes:

```bash
sudo chown -R $USER:$USER ./backend ./frontend
```

### Container Won't Start

Check logs for errors:

```bash
docker-compose logs <service-name>
```

Common issues:

- Missing environment variables
- Port conflicts
- Dependency installation failures

### Clear Everything and Start Fresh

```bash
docker-compose down -v
docker system prune -f
docker-compose up --build
```

## Production Notes

This setup is optimized for development. For production:

1. Remove volume mounts for source code
2. Set appropriate environment variables
3. Use production-optimized images
4. Add proper health checks
5. Configure reverse proxy (Nginx)
6. Set up proper logging and monitoring
