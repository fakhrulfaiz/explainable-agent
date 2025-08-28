# Explainable Agent

An intelligent agent system with explainable AI features, built with FastAPI backend and React TypeScript frontend. The system provides transparent AI decision-making processes with interactive explanations.

## 🚀 Features

- **Explainable AI**: Transparent decision-making with step-by-step explanations
- **Interactive Chat Interface**: Real-time conversation with the AI agent
- **Approval Workflow**: Human-in-the-loop decision making
- **Agent Streaming**: Real-time agent responses with streaming support
- **LangGraph Integration**: Advanced agent workflow management
- **Docker Support**: Easy deployment with Docker containers
- **RESTful API**: FastAPI backend with automatic documentation

## 🏗️ Architecture

- **Backend**: FastAPI with LangGraph for agent orchestration
- **Frontend**: React TypeScript with Vite and Tailwind CSS
- **Reverse Proxy**: Nginx for routing and load balancing
- **Containerization**: Docker and Docker Compose for easy deployment

## 📋 Prerequisites

- [Docker](https://www.docker.com/get-started) (v20.0 or higher)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0 or higher)
- [Git](https://git-scm.com/downloads)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/fakhrulfaiz/explainable-agent.git
cd explainable-agent
```

### 2. Environment Setup

#### Backend Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
# Copy the example environment file
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your configuration:

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
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost

# LangSmith Configuration (optional)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=explainable-agent
```

#### Frontend Environment Variables

Create a `.env` file in the `frontend/` directory:

```bash
# Copy the example environment file
cp frontend/.env.example frontend/.env
```

Edit `frontend/.env`:

```env
# API Configuration
VITE_API_URL=http://localhost/api
VITE_DEV_MODE=true

# Feature Flags
VITE_ENABLE_APPROVAL_WORKFLOW=true
VITE_ENABLE_STREAMING=true
```

### 3. Run with Docker (Recommended)

#### Production Mode

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Development Mode

```bash
# Start in development mode with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 4. Access the Application

- **Frontend**: http://localhost
- **Backend API**: http://localhost/api
- **API Documentation**: http://localhost/api/docs
- **Redoc Documentation**: http://localhost/api/redoc

## 🛠️ Development Setup

### Prerequisites for Local Development

- Python 3.11+
- Node.js 18+
- npm or yarn

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

## 📚 API Documentation

The API documentation is automatically generated and available at:

- **Swagger UI**: http://localhost/api/docs
- **ReDoc**: http://localhost/api/redoc

### Key Endpoints

- `GET /health` - Health check
- `POST /api/chat` - Simple chat with agent
- `POST /api/chat/stream` - Streaming chat
- `POST /api/chat/approval` - Chat with approval workflow
- `GET /api/graph/state` - Get agent graph state
- `POST /api/graph/interrupt` - Interrupt agent execution

## 🧪 Testing

### Backend Tests

```bash
cd backend
python -m pytest
```

### Frontend Tests

```bash
cd frontend
npm test
```

## 🐳 Docker Commands

### Useful Docker Commands

```bash
# Build specific service
docker-compose build backend

# View service logs
docker-compose logs backend
docker-compose logs frontend

# Execute commands in running container
docker-compose exec backend bash
docker-compose exec frontend sh

# Remove all containers and volumes
docker-compose down -v

# Rebuild and restart
docker-compose up --build -d
```

### Development vs Production

- **Development**: Hot reload enabled, source code mounted as volumes
- **Production**: Optimized builds, no source code mounting

## 📁 Project Structure

```
explainable-agent/
├── backend/                    # FastAPI backend
│   ├── src/
│   │   ├── models/            # Data models and schemas
│   │   ├── services/          # Business logic and agent services
│   │   ├── nodes/             # LangGraph nodes
│   │   └── tools/             # Agent tools
│   ├── routers/               # API route handlers
│   ├── requirements.txt       # Python dependencies
│   └── server.py             # FastAPI application entry point
├── frontend/                  # React TypeScript frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/            # Page components
│   │   ├── api/              # API client and services
│   │   └── types/            # TypeScript type definitions
│   └── package.json          # Node.js dependencies
├── nginx/                     # Nginx configuration
├── docker-compose.yml         # Production Docker setup
├── docker-compose.dev.yml     # Development overrides
└── README.md                 # This file
```

## 🔧 Configuration

### Environment Variables Reference

#### Backend Variables

| Variable           | Required | Default                           | Description                              |
| ------------------ | -------- | --------------------------------- | ---------------------------------------- |
| `OPENAI_API_KEY`   | Yes      | -                                 | OpenAI API key for GPT models            |
| `DEEPSEEK_API_KEY` | No       | -                                 | DeepSeek API key (alternative to OpenAI) |
| `DATABASE_URL`     | No       | `sqlite:///./src/resource/art.db` | Database connection string               |
| `ENVIRONMENT`      | No       | `development`                     | Application environment                  |
| `DEBUG`            | No       | `true`                            | Enable debug mode                        |
| `LOG_LEVEL`        | No       | `INFO`                            | Logging level                            |
| `ALLOWED_ORIGINS`  | No       | `*`                               | CORS allowed origins                     |

#### Frontend Variables

| Variable                        | Required | Default                | Description                 |
| ------------------------------- | -------- | ---------------------- | --------------------------- |
| `VITE_API_URL`                  | No       | `http://localhost/api` | Backend API URL             |
| `VITE_DEV_MODE`                 | No       | `false`                | Enable development features |
| `VITE_ENABLE_APPROVAL_WORKFLOW` | No       | `true`                 | Enable approval workflow UI |
| `VITE_ENABLE_STREAMING`         | No       | `true`                 | Enable streaming chat       |

## 🚨 Troubleshooting

### Common Issues

1. **Port Already in Use**

   ```bash
   # Check what's using port 80
   netstat -tulpn | grep :80

   # Use different port
   docker-compose up -d --scale nginx=0
   # Then access backend directly at http://localhost:8000
   ```

2. **Permission Denied (Linux/Mac)**

   ```bash
   sudo chown -R $USER:$USER ./backend/logs
   ```

3. **Module Not Found Errors**

   ```bash
   # Rebuild containers
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

4. **Frontend Not Loading**
   - Check if all environment variables are set
   - Verify API_URL points to correct backend
   - Check browser console for errors

### Logs and Debugging

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs backend
docker-compose logs frontend
docker-compose logs nginx

# Follow logs in real-time
docker-compose logs -f backend
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangChain](https://langchain.com/) for the agent framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) for agent workflow management
- [FastAPI](https://fastapi.tiangolo.com/) for the backend framework
- [React](https://reactjs.org/) for the frontend framework
- [Tailwind CSS](https://tailwindcss.com/) for styling

## 📞 Support

If you encounter any issues or have questions, please:

1. Check the [troubleshooting section](#-troubleshooting)
2. Search existing [GitHub Issues](https://github.com/fakhrulfaiz/explainable-agent/issues)
3. Create a new issue with detailed information about your problem

---

**Happy coding! 🚀**
