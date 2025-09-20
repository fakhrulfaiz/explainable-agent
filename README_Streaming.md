# LangGraph Streaming Implementation

This implementation adds real-time streaming capabilities to your LangGraph backend, allowing you to show internal AI messages and progress updates to users in real-time.

## Backend Changes

### New Endpoints Added

1. **`POST /graph/start/stream`** - Start graph execution with streaming
2. **`POST /graph/resume/stream`** - Resume graph execution with streaming

### Event Types

The streaming endpoints send Server-Sent Events (SSE) with the following event types:

```json
{
  "type": "status",
  "data": {
    "thread_id": "uuid",
    "status": "starting|resuming",
    "message": "Human readable status"
  }
}
```

```json
{
  "type": "ai_thinking",
  "data": {
    "content": "Internal AI reasoning/thinking",
    "temporary": true,
    "timestamp": "ISO timestamp"
  }
}
```

```json
{
  "type": "plan_update",
  "data": {
    "plan": "Updated execution plan",
    "timestamp": "ISO timestamp"
  }
}
```

```json
{
  "type": "step_progress",
  "data": {
    "completed_steps": 3,
    "latest_step": {...},
    "timestamp": "ISO timestamp"
  }
}
```

```json
{
  "type": "waiting_feedback",
  "data": {
    "status": "user_feedback",
    "thread_id": "uuid",
    "plan": "Plan requiring approval",
    "assistant_response": "Response text"
  }
}
```

```json
{
  "type": "completed",
  "data": {
    "status": "finished",
    "thread_id": "uuid",
    "final_response": "Final answer",
    "steps": [...],
    "plan": "Final plan"
  }
}
```

```json
{
  "type": "error",
  "data": {
    "error": "Error message",
    "thread_id": "uuid",
    "timestamp": "ISO timestamp"
  }
}
```

## Frontend Integration

### Key Features

1. **Real-time AI Thinking**: Shows internal AI messages temporarily under a "Generating..." indicator
2. **Progressive Updates**: Plan updates, step progress, and status changes in real-time
3. **User Feedback Flow**: Seamless approval/rejection interface
4. **Error Handling**: Graceful error display and recovery

### Usage Examples

#### Basic Usage (Simple)

```jsx
import SimpleStreamingExample from "./SimpleStreamingExample";

function App() {
  return <SimpleStreamingExample />;
}
```

#### Advanced Usage (Full Featured)

```jsx
import StreamingGraphComponent from "./StreamingGraphComponent";

function App() {
  return <StreamingGraphComponent />;
}
```

#### Custom Hook Usage

```jsx
import { useGraphStream } from "./StreamingGraphComponent";

function MyComponent() {
  const {
    status,
    internalMessage,
    showInternal,
    finalResponse,
    startStream,
    resumeStream,
  } = useGraphStream();

  return (
    <div>
      {status === "generating" && (
        <div>
          <span>AI is working...</span>
          {showInternal && (
            <div className="temporary-message">{internalMessage}</div>
          )}
        </div>
      )}

      {finalResponse && <div>{finalResponse}</div>}
    </div>
  );
}
```

## UI/UX Design Pattern

The key design pattern is:

1. **Permanent Status**: Show main status (Generating, Completed, etc.)
2. **Temporary Internal Messages**: Show AI thinking/reasoning under the status, auto-hide after 3-4 seconds
3. **Progressive Disclosure**: Reveal plan, steps, and final response as they become available
4. **Interactive Feedback**: Clear approval/rejection interface when needed

### Visual Hierarchy

```
[Main Status: "Generating..."]
├── [Temporary AI Message] ← Auto-hides
├── [Plan] ← Appears when ready
├── [Step Progress] ← Updates in real-time
└── [Final Response] ← Appears when complete
```

## Styling Recommendations

```css
/* Main status indicator */
.status-indicator {
  /* Always visible, permanent */
  position: sticky;
  top: 0;
}

/* Temporary AI thinking */
.ai-thinking {
  /* Subtle, temporary, under main status */
  opacity: 0.8;
  font-style: italic;
  animation: fadeInOut 3s ease-in-out;
}

/* Progressive content */
.plan,
.steps,
.response {
  /* Appear smoothly as they become available */
  transition: all 0.3s ease-in-out;
}
```

## Benefits

1. **Better UX**: Users see progress instead of blank loading states
2. **Transparency**: Internal AI reasoning is visible but not overwhelming
3. **Real-time Feedback**: No need for polling or manual refresh
4. **Responsive**: Updates appear immediately as they happen
5. **Scalable**: SSE handles multiple concurrent streams efficiently

## Backward Compatibility

Your existing non-streaming endpoints (`/start` and `/resume`) remain unchanged. The streaming endpoints are additional options that clients can choose to use.

## Error Handling

- Stream automatically closes on completion or error
- Client reconnection is handled by the browser
- Graceful degradation if streaming is not supported
- Clear error messages in the stream

## Testing

Test your streaming implementation by:

1. Starting a complex query that takes time
2. Watching for internal AI messages
3. Verifying approval flows work correctly
4. Testing error scenarios
5. Checking multiple concurrent streams

The implementation provides a much better user experience while maintaining the robustness of your existing LangGraph system.
