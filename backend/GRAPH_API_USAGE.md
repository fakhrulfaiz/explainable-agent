# Graph-Based API Implementation

This document explains how to use the new graph-based API that implements a human-in-the-loop workflow similar to the reference pattern you provided.

## API Endpoints

### 1. Start Graph Execution

**POST** `/graph/start`

Starts a new graph execution that will pause for human approval.

**Request:**

```json
{
  "human_request": "How many paintings are in the database?"
}
```

**Response:**

```json
{
  "thread_id": "uuid-string",
  "run_status": "user_feedback",
  "assistant_response": "Plan for your request...",
  "plan": "Detailed execution plan..."
}
```

### 2. Resume Graph Execution

**POST** `/graph/resume`

Resumes execution after human feedback.

**Request:**

```json
{
  "thread_id": "uuid-string",
  "review_action": "approved", // or "feedback" or "cancelled"
  "human_comment": "Optional feedback text"
}
```

**Response:**

```json
{
  "thread_id": "uuid-string",
  "run_status": "finished",
  "assistant_response": "Final result...",
  "steps": [...],
  "final_result": {...}
}
```

### 3. Get Graph Status

**GET** `/graph/status/{thread_id}`

Gets the current status of a graph execution.

**Response:**

```json
{
  "thread_id": "uuid-string",
  "status": "user_feedback",
  "next_nodes": ["human_feedback"],
  "plan": "Current plan...",
  "step_count": 2,
  "current_status": "approved"
}
```

## Workflow

1. **User submits a query** → API creates a plan and pauses for approval
2. **Human reviews plan** → Can approve, provide feedback, or cancel
3. **If approved** → Execution continues and completes
4. **If feedback** → Plan is revised and approval is requested again
5. **If cancelled** → Execution stops

## Frontend Integration

The `ChatWithApproval` component has been updated to use this new API:

### Key Features:

- **Thread Management**: Each conversation maintains a unique thread ID
- **Approval Workflow**: Messages requiring approval show with special buttons
- **Real-time Status**: Shows current thread and approval status
- **Error Handling**: Graceful error handling and user feedback

### Usage in React:

```typescript
import { GraphService } from "../api/services/graphService";

// Start a new conversation
const response = await GraphService.startGraph({
  human_request: "Your question here",
});

// Approve a plan
await GraphService.approveAndContinue(threadId);

// Provide feedback
await GraphService.provideFeedbackAndContinue(threadId, "Your feedback");

// Cancel execution
await GraphService.cancelExecution(threadId);
```

## Testing

1. **Start the backend server:**

   ```bash
   cd backend
   python server.py
   ```

2. **Start the frontend:**

   ```bash
   cd frontend
   npm run dev
   ```

3. **Test the workflow:**
   - Navigate to the Chat with Approval page
   - Ask a database question like "How many paintings are in the database?"
   - Review the generated plan
   - Approve or provide feedback
   - See the final results

## Key Differences from Original

This implementation extends the reference pattern with:

- **Enhanced Response Models**: More detailed response information
- **Frontend Integration**: Complete React component integration
- **Error Handling**: Comprehensive error handling and status tracking
- **Thread Management**: Better thread lifecycle management
- **Status Monitoring**: Real-time status checking capabilities

## Example Workflow

1. User: "Show me 3 paintings from the database"
2. System: Generates plan → "I'll query the paintings table and show 3 rows"
3. User: Approves the plan
4. System: Executes → Queries database and returns results
5. User: Sees formatted results with execution details

This creates a transparent, controllable AI interaction where users can review and approve AI actions before execution.
