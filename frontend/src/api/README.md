# API Directory

This directory contains all API-related code for the frontend application, organized for scalability and maintainability.

## 📁 Structure

```
src/api/
├── client.ts              # Axios client configuration
├── types.ts              # TypeScript type definitions
├── endpoints.ts          # API endpoint constants
├── services/             # Service classes for different API modules
│   ├── chatService.ts    # Chat-related API calls
│   ├── agentService.ts   # Agent/query API calls
│   ├── approvalService.ts # Approval workflow API calls
│   └── index.ts          # Service exports
├── index.ts              # Main API exports
└── README.md             # This file
```

## 🚀 Usage

### Basic Import

```typescript
import { chatService, agentService, approvalService } from "../api";
```

### Individual Service Import

```typescript
import { chatService } from "../api/services/chatService";
```

### Using the API Client Directly

```typescript
import { apiClient } from "../api/client";
```

## 🔧 Services

### ChatService

Handles chat-related API calls:

```typescript
// Send a message
const response = await chatService.sendMessage({
  message: "Hello",
  history: [],
});

// Get chat history
const history = await chatService.getChatHistory();
```

### AgentService

Handles explainable agent queries:

```typescript
// Send a query
const response = await agentService.sendQuery({
  query: "What is machine learning?",
});

// Enhanced query with explanations
const enhanced = await agentService.sendEnhancedQuery({
  query: "Explain neural networks",
});
```

### ApprovalService

Handles message approval workflow:

```typescript
// Approve a message
await approvalService.approveMessage("msg-123", "Great response!");

// Disapprove with feedback
await approvalService.disapproveMessage(
  "msg-123",
  "Needs improvement",
  "More detail needed"
);
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
VITE_API_URL=http://localhost:8000/api
VITE_NODE_ENV=development
VITE_API_TIMEOUT=30000
```

### API Client Features

- **Automatic retries** for failed requests
- **Request/response interceptors** for logging and auth
- **Error handling** with consistent error format
- **TypeScript support** with full type safety

## 🔗 Backend Integration

This API structure matches your backend endpoints:

- `/api/query` - Basic query endpoint
- `/api/enhanced-query` - Enhanced query with explanations
- `/api/chat` - Chat functionality
- `/api/approval/*` - Approval workflow
- `/api/health` - Health check

## 📝 Type Safety

All API calls are fully typed:

- Request payloads
- Response data
- Error handling
- Service methods

## 🛠️ Adding New Services

1. Create a new service file in `services/`
2. Define the service class with methods
3. Export from `services/index.ts`
4. Add any new types to `types.ts`
5. Add endpoints to `endpoints.ts`

Example:

```typescript
// services/newService.ts
import { apiClient } from "../client";
import { API_ENDPOINTS } from "../endpoints";

export class NewService {
  async newMethod(): Promise<any> {
    return apiClient.get(API_ENDPOINTS.NEW_ENDPOINT);
  }
}

export const newService = new NewService();
```
