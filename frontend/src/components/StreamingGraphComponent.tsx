import React, { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Brain, CheckCircle, XCircle, AlertCircle, Play, RotateCcw } from "lucide-react";

/**
 * Custom hook for managing Server-Sent Events (SSE) streaming
 * from the LangGraph backend
 */
const useGraphStream = () => {
  const [status, setStatus] = useState<string>("idle");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [internalMessage, setInternalMessage] = useState<string>("");
  const [showInternal, setShowInternal] = useState<boolean>(false);
  const [plan, setPlan] = useState<string>("");
  const [steps, setSteps] = useState<any[]>([]);
  const [finalResponse, setFinalResponse] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const internalTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Clean up function
  const cleanup = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (internalTimeoutRef.current) {
      clearTimeout(internalTimeoutRef.current);
      internalTimeoutRef.current = null;
    }
    setIsStreaming(false);
  };

  // Function to start streaming a new graph execution
  const startStream = async (query: string, existingThreadId: string | null = null) => {
    cleanup();

    setStatus("starting");
    setError(null);
    setFinalResponse("");
    setSteps([]);
    setPlan("");
    setIsStreaming(true);

    try {
      // Create the request payload
      const payload = {
        human_request: query,
        ...(existingThreadId && { thread_id: existingThreadId }),
      };

      // Since EventSource doesn't support POST directly, we need to use fetch with SSE
      const response = await fetch("http://localhost/api/graph/start/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Create a reader for the stream
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Response body is null");
      }
      const decoder = new TextDecoder();

      const readStream = async () => {
        try {
          let buffer = "";
          
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            
            // Split by double newlines to get complete SSE events
            const events = buffer.split("\n\n");
            buffer = events.pop() || ""; // Keep incomplete event in buffer
            
            for (const event of events) {
              if (event.trim()) {
                // Simplified: find the data line and parse it directly
                const dataMatch = event.match(/^data: (.+)$/m);
                if (dataMatch) {
                  try {
                    const eventData = JSON.parse(dataMatch[1]);
                    handleStreamEvent(eventData);
                  } catch (parseError) {
                    console.error("Error parsing SSE data:", parseError, "Data:", dataMatch[1]);
                  }
                }
              }
            }
          }
        } catch (streamError) {
          console.error("Stream reading error:", streamError);
          setError((streamError as Error).message);
        } finally {
          setIsStreaming(false);
        }
      };

      readStream();
    } catch (fetchError) {
      console.error("Failed to start stream:", fetchError);
      setError((fetchError as Error).message);
      setIsStreaming(false);
    }
  };

  // Function to resume streaming after user feedback
  const resumeStream = async (threadId: string, action: string, comment: string | null = null) => {
    cleanup();

    setStatus("resuming");
    setError(null);
    setIsStreaming(true);

    try {
      const payload = {
        thread_id: threadId,
        review_action: action,
        ...(comment && { human_comment: comment }),
      };

      const response = await fetch("http://localhost/api/graph/resume/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Response body is null");
      }
      const decoder = new TextDecoder();

      const readStream = async () => {
        try {
          let buffer = "";
          
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            
            // Split by double newlines to get complete SSE events
            const events = buffer.split("\n\n");
            buffer = events.pop() || ""; // Keep incomplete event in buffer
            
            for (const event of events) {
              if (event.trim()) {
                // Simplified: find the data line and parse it directly
                const dataMatch = event.match(/^data: (.+)$/m);
                if (dataMatch) {
                  try {
                    const eventData = JSON.parse(dataMatch[1]);
                    handleStreamEvent(eventData);
                  } catch (parseError) {
                    console.error("Error parsing SSE data:", parseError, "Data:", dataMatch[1]);
                  }
                }
              }
            }
          }
        } catch (streamError) {
          console.error("Stream reading error:", streamError);
          setError((streamError as Error).message);
        } finally {
          setIsStreaming(false);
        }
      };

      readStream();
    } catch (fetchError) {
      console.error("Failed to resume stream:", fetchError);
      setError((fetchError as Error).message);
      setIsStreaming(false);
    }
  };

  // Handle incoming stream events
  const handleStreamEvent = (eventData: any) => {
    const { type, data } = eventData;

    switch (type) {
      case "status":
        setStatus(data.status);
        if (data.thread_id) {
          setThreadId(data.thread_id);
        }
        break;

      case "ai_thinking":
        // Show internal AI message temporarily
        setInternalMessage(data.content);
        setShowInternal(true);

        // Clear any existing timeout
        if (internalTimeoutRef.current) {
          clearTimeout(internalTimeoutRef.current);
        }

        // Auto-hide after 4 seconds
        internalTimeoutRef.current = setTimeout(() => {
          setShowInternal(false);
          setInternalMessage("");
        }, 4000);
        break;

      case "plan_update":
        setPlan(data.plan);
        setStatus("planning");
        break;

      case "step_progress":
        setSteps((prevSteps) => {
          // Update steps array with new completed steps
          const newSteps = [...prevSteps];
          if (
            data.latest_step &&
            !newSteps.find((s) => s.id === data.latest_step.id)
          ) {
            newSteps.push(data.latest_step);
          }
          return newSteps;
        });
        setStatus("executing");
        break;

      case "assistant_response":
        setFinalResponse(data.response);
        break;

      case "waiting_feedback":
        setStatus("awaiting_approval");
        if (data.plan) setPlan(data.plan);
        if (data.assistant_response) setFinalResponse(data.assistant_response);
        break;

      case "completed":
        setStatus("completed");
        setFinalResponse(data.final_response);
        if (data.steps) setSteps(data.steps);
        if (data.plan) setPlan(data.plan);
        setIsStreaming(false);
        break;

      case "error":
        setError(data.error);
        setStatus("error");
        setIsStreaming(false);
        break;

      default:
        console.log("Unknown event type:", type, data);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, []);

  return {
    // State
    status,
    threadId,
    internalMessage,
    showInternal,
    plan,
    steps,
    finalResponse,
    error,
    isStreaming,

    // Actions
    startStream,
    resumeStream,
    cleanup,
  };
};

/**
 * Status icon component
 */
const StatusIcon = ({ status, isStreaming }: { status: string; isStreaming: boolean }) => {
  if (isStreaming) {
    return <Loader2 className="h-4 w-4 animate-spin" />;
  }

  switch (status) {
    case "completed":
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case "error":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "awaiting_approval":
      return <AlertCircle className="h-4 w-4 text-purple-500" />;
    default:
      return <Brain className="h-4 w-4 text-blue-500" />;
  }
};

/**
 * Main component for streaming graph execution
 */
const StreamingGraphComponent: React.FC = () => {
  const {
    status,
    threadId,
    internalMessage,
    showInternal,
    plan,
    steps,
    finalResponse,
    error,
    isStreaming,
    startStream,
    resumeStream,
    cleanup,
  } = useGraphStream();

  const [query, setQuery] = useState<string>("");
  const [userComment, setUserComment] = useState<string>("");

  const handleStartQuery = () => {
    if (query.trim()) {
      startStream(query.trim());
    }
  };

  const handleApprove = () => {
    if (threadId) {
      resumeStream(threadId, "approved", userComment.trim() || null);
      setUserComment("");
    }
  };

  const handleReject = () => {
    if (threadId) {
      resumeStream(
        threadId,
        "cancelled",
        userComment.trim() || "User rejected the plan"
      );
      setUserComment("");
    }
  };

  const handleFeedback = () => {
    if (threadId && userComment.trim()) {
      resumeStream(threadId, "feedback", userComment.trim());
      setUserComment("");
    }
  };

  const getStatusMessage = () => {
    switch (status) {
      case "idle":
        return "Ready to start";
      case "starting":
        return "Initializing...";
      case "planning":
        return "Creating execution plan...";
      case "executing":
        return "Executing steps...";
      case "awaiting_approval":
        return "Waiting for your approval";
      case "completed":
        return "Execution completed";
      case "error":
        return "Error occurred";
      case "resuming":
        return "Resuming execution...";
      default:
        return status;
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            LangGraph Streaming Interface
          </CardTitle>
          <CardDescription>
            Experience real-time AI reasoning and execution with streaming updates
          </CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {/* Query Input */}
          <div className="space-y-2">
            <Label htmlFor="query">Your Query</Label>
            <div className="flex gap-2">
              <Input
                id="query"
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter your question or request..."
                disabled={isStreaming}
                onKeyDown={(e) => e.key === "Enter" && handleStartQuery()}
                className="flex-1"
              />
              <Button
                onClick={handleStartQuery}
                disabled={isStreaming || !query.trim()}
                className="min-w-[100px]"
              >
                {isStreaming ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                {isStreaming ? "Processing" : "Start"}
              </Button>
            </div>
          </div>

          {/* Status Display */}
          <Card className="bg-muted/30">
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <StatusIcon status={status} isStreaming={isStreaming} />
                <div>
                  <div className="font-medium">{getStatusMessage()}</div>
                  {threadId && (
                    <div className="text-xs text-muted-foreground">
                      Thread ID: {threadId}
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Internal AI Thinking (Temporary Display) */}
          {showInternal && internalMessage && (
            <Card className="border-blue-200 bg-blue-50/50">
              <CardContent className="pt-4">
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 animate-pulse" />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-blue-800 mb-1">
                      AI is thinking...
                    </div>
                    <div className="text-sm text-blue-700 italic">
                      {internalMessage}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Plan Display */}
          {plan && (
            <Card className="border-yellow-200 bg-yellow-50/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg text-yellow-800">
                  Execution Plan
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-yellow-700 whitespace-pre-wrap">
                  {plan}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Steps Progress */}
          {steps.length > 0 && (
            <Card className="border-green-200 bg-green-50/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg text-green-800">
                  Execution Steps ({steps.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {steps.map((step, index) => (
                    <div
                      key={step.id || index}
                      className="flex items-center gap-2"
                    >
                      <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                      <span className="text-sm text-green-700">
                        Step {index + 1}: {step.type || "Unknown"} -{" "}
                        {step.decision || "Completed"}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Approval Interface */}
          {status === "awaiting_approval" && (
            <Card className="border-purple-200 bg-purple-50/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg text-purple-800">
                  Approval Required
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="comment">Optional Comment</Label>
                  <textarea
                    id="comment"
                    value={userComment}
                    onChange={(e) => setUserComment(e.target.value)}
                    placeholder="Add any feedback or modifications..."
                    rows={3}
                    className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div className="flex gap-3">
                  <Button onClick={handleApprove} className="bg-green-600 hover:bg-green-700">
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Approve
                  </Button>
                  <Button
                    onClick={handleFeedback}
                    disabled={!userComment.trim()}
                    variant="outline"
                    className="border-yellow-600 text-yellow-600 hover:bg-yellow-50"
                  >
                    Provide Feedback
                  </Button>
                  <Button
                    onClick={handleReject}
                    variant="destructive"
                  >
                    <XCircle className="h-4 w-4 mr-2" />
                    Reject
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Final Response */}
          {finalResponse && status === "completed" && (
            <Card className="border-green-200 bg-green-50/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg text-green-800">
                  Final Response
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-green-700 whitespace-pre-wrap">
                  {finalResponse}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error Display */}
          {error && (
            <Card className="border-red-200 bg-red-50/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg text-red-800 flex items-center gap-2">
                  <XCircle className="h-5 w-5" />
                  Error
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-red-700">{error}</div>
              </CardContent>
            </Card>
          )}

          {/* Reset Button */}
          {(status === "completed" || status === "error") && (
            <div className="flex justify-center">
              <Button
                onClick={() => {
                  cleanup();
                  setQuery("");
                  setUserComment("");
                }}
                variant="outline"
                className="gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                Start New Query
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default StreamingGraphComponent;
