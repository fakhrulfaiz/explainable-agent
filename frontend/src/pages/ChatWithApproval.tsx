import React, { useState } from 'react';
import { ChatComponent } from '../components';
import { Message } from '../types/chat';
import { GraphService } from '../api/services/graphService';

const ChatWithApproval: React.FC = () => {
  const [chatKey, setChatKey] = useState<number>(0); // For resetting chat
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState<{
    threadId: string;
    plan: string;
    messageId: number;
  } | null>(null);

  // Handle sending messages using the graph API
  const handleSendMessage = async (message: string, messageHistory: Message[]): Promise<string> => {
    try {
      // Start a new graph execution
      const response = await GraphService.startGraph({
        human_request: message
      });

      // Store thread ID for future operations
      setCurrentThreadId(response.thread_id);

      if (response.run_status === 'user_feedback') {
        // Need human approval for the plan
        const plan = response.plan || response.assistant_response || 'Plan generated - awaiting approval';
        
        // Store pending approval info
        setPendingApproval({
          threadId: response.thread_id,
          plan,
          messageId: messageHistory.length + 1 // Next message ID
        });

        return `**Plan for your request:**\n\n${plan}\n\n**This plan requires your approval before execution.**`;
      } else if (response.run_status === 'finished') {
        // Execution completed without approval needed
        return response.assistant_response || 'Task completed successfully.';
      } else if (response.run_status === 'error') {
        throw new Error(response.error || 'An error occurred while processing your request.');
      }

      return response.assistant_response || 'Processing...';
    } catch (error) {
      console.error('Error in handleSendMessage:', error);
      throw error;
    }
  };

  // Handle approval
  const handleApprove = async (_content: string, message: Message): Promise<string> => {
    console.log('Approval attempt:', { pendingApproval, messageId: message.id });
    
    // Use current thread if available, or try to approve the message if it needs approval
    const threadId = pendingApproval?.threadId || currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to approve');
    }

    try {
      console.log('Approving plan for thread:', threadId);
      
      const response = await GraphService.approveAndContinue(threadId);
      
      setPendingApproval(null);
      
      if (response.run_status === 'finished') {
        // Return the final result to be displayed in chat
        const finalResponse = response.assistant_response || 'Task completed successfully.';
        
        // Add step information if available
        let detailedResponse = finalResponse;
        if (response.steps && response.steps.length > 0) {
          detailedResponse += `\n\n**Execution Summary:**\n`;
          detailedResponse += `- Steps executed: ${response.steps.length}\n`;
          if (response.overall_confidence) {
            detailedResponse += `- Overall confidence: ${(response.overall_confidence * 100).toFixed(1)}%\n`;
          }
          if (response.total_time) {
            detailedResponse += `- Total time: ${response.total_time.toFixed(2)}s\n`;
          }
        }
        
        return detailedResponse;
        
      } else if (response.run_status === 'error') {
        throw new Error(response.error || 'An error occurred during execution');
      } else {
        return response.assistant_response || 'Execution in progress...';
      }
      
    } catch (error) {
      console.error('Error approving plan:', error);
      throw error;
    }
  };

 
  // Handle feedback (when user provides revision comments)
  const handleDisapprove = async (content: string, message: Message): Promise<string> => {
    console.log('Feedback attempt:', { pendingApproval, messageId: message.id, feedback: content });
    
    // Use current thread if available, or try to provide feedback for the message
    const threadId = pendingApproval?.threadId || currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to provide feedback for');
    }

    try {
      console.log('Providing feedback for thread:', threadId);
      
      // Provide feedback and continue execution
      const response = await GraphService.provideFeedbackAndContinue(threadId, content);
      
      // Clear pending approval
      setPendingApproval(null);
      
      if (response.run_status === 'user_feedback') {
        // New plan generated, need approval again
        const newPlan =  response.assistant_response || response.plan || 'Revised plan generated - awaiting approval';
        
        // Set up pending approval info for the revised plan - we'll update the messageId via callback
        setPendingApproval({
          threadId: response.thread_id,
          plan: newPlan,
          messageId: 0 // Will be updated by onMessageCreated callback
        });
        
        return `**Revised Plan:**\n\n${newPlan}\n\n⚠️ **This revised plan requires your approval before execution.**`;
        
      } else if (response.run_status === 'finished') {
        // Execution completed after feedback
        const finalResponse = response.assistant_response || 'Task completed successfully after feedback.';
        
        // Add step information if available
        let detailedResponse = finalResponse;
        if (response.steps && response.steps.length > 0) {
          detailedResponse += `\n\n**Execution Summary:**\n`;
          detailedResponse += `- Steps executed: ${response.steps.length}\n`;
          if (response.overall_confidence) {
            detailedResponse += `- Overall confidence: ${(response.overall_confidence * 100).toFixed(1)}%\n`;
          }
          if (response.total_time) {
            detailedResponse += `- Total time: ${response.total_time.toFixed(2)}s\n`;
          }
        }
        
        return detailedResponse;
        
      } else if (response.run_status === 'error') {
        throw new Error(response.error || 'An error occurred during execution');
      } else {
        return response.assistant_response || 'Processing feedback...';
      }
      
    } catch (error) {
      console.error('Error providing feedback:', error);
      throw error;
    }
  };

  // Handle cancellation (separate from feedback)
  const handleCancel = async (_content: string, message: Message): Promise<string> => {
    console.log('Cancel attempt:', { pendingApproval, messageId: message.id });
    
    // Use current thread if available, or try to cancel the message if it needs approval
    const threadId = pendingApproval?.threadId || currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to cancel');
    }

    try {
      console.log('Cancelling execution for thread:', threadId);
      
      // Cancel the execution
      await GraphService.cancelExecution(threadId);
      
      // Clear pending approval
      setPendingApproval(null);
      
      return `❌ **Execution Cancelled**\n\nThe task has been cancelled and will not be executed.`;
      
    } catch (error) {
      console.error('Error cancelling execution:', error);
      throw error;
    }
  };

  // Handle retry for timed-out operations
  const handleRetry = async (message: Message): Promise<string | void> => {
    console.log('Retry attempt:', { messageId: message.id, retryAction: message.retryAction, threadId: message.threadId });
    
    const threadId = message.threadId || currentThreadId;
    
    if (!threadId) {
      throw new Error('No thread ID available for retry');
    }

    try {
      let response;
      
      if (message.retryAction === 'approve') {
        console.log('Retrying approval for thread:', threadId);
        response = await GraphService.approveAndContinue(threadId);
      } else if (message.retryAction === 'disapprove') {
        console.log('Retrying feedback for thread:', threadId);
        // For disapprove retry, we might need the original feedback text
        // For now, we'll use a generic retry message
        response = await GraphService.provideFeedbackAndContinue(threadId, 'Retrying previous action');
      } else {
        throw new Error('Unknown retry action');
      }

      // Clear pending approval since we're retrying
      setPendingApproval(null);
      
      // Handle the response similar to the original handlers
      if (response.run_status === 'finished') {
        const finalResponse = response.assistant_response || 'Task completed successfully after retry.';
        
        let detailedResponse = finalResponse;
        if (response.steps && response.steps.length > 0) {
          detailedResponse += `\n\n**Execution Summary:**\n`;
          detailedResponse += `- Steps executed: ${response.steps.length}\n`;
          if (response.overall_confidence) {
            detailedResponse += `- Overall confidence: ${(response.overall_confidence * 100).toFixed(1)}%\n`;
          }
          if (response.total_time) {
            detailedResponse += `- Total time: ${response.total_time.toFixed(2)}s\n`;
          }
        }
        
        return detailedResponse;
        
      } else if (response.run_status === 'user_feedback') {
        const newPlan = response.assistant_response || response.plan || 'New plan generated after retry - awaiting approval';
        
        setPendingApproval({
          threadId: response.thread_id,
          plan: newPlan,
          messageId: 0 // Will be updated by onMessageCreated callback
        });
        
        return `**Plan after retry:**\n\n${newPlan}\n\n⚠️ **This plan requires your approval before execution.**`;
        
      } else if (response.run_status === 'error') {
        throw new Error(response.error || 'An error occurred during retry');
      }
      
      return response.assistant_response || 'Retry completed.';
      
    } catch (error) {
      console.error('Error during retry:', error);
      throw error;
    }
  };

  // Handle when a new message that needs approval is created
  const handleMessageCreated = (messageId: number) => {
    if (pendingApproval && pendingApproval.messageId === 0) {
      // Update the pending approval with the new message ID
      setPendingApproval(prev => prev ? { ...prev, messageId } : null);
    }
  };

  return (
    <div style={{ height: '100%', padding: '0 0.5rem', display: 'flex', flexDirection: 'column' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: '#1f2937', marginBottom: '0.5rem' }}>
            Explainable Agent Chat
          </h1>
        </div>

        {/* Chat Container */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ backgroundColor: 'white', borderRadius: '0.5rem', boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)', height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">Chat with Approval</h2>
              <p className="text-sm text-gray-600">Messages require approval/disapproval for AI learning</p>
            </div>
            <div className="flex-1 min-h-0">
              <ChatComponent
                key={`chat-approval-${chatKey}`}
                onSendMessage={handleSendMessage}
                onApprove={handleApprove}
                onDisapprove={handleDisapprove}
                onCancel={handleCancel}
                onRetry={handleRetry}
                onMessageCreated={handleMessageCreated}
                currentThreadId={currentThreadId}
                placeholder="Ask me anything..."
                showApprovalButtons={true}
                className="h-full"
              />
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="mt-4 text-center">
          <button
            onClick={() => {
              setChatKey(prev => prev + 1);
              setCurrentThreadId(null);
              setPendingApproval(null);
            }}
            className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors mr-4"
          >
            Reset Chat
          </button>
          {currentThreadId && (
            <span className="text-xs text-gray-500 mr-4">
              Thread: {currentThreadId.slice(0, 8)}...
            </span>
          )}
          {pendingApproval && (
            <span className="text-xs text-orange-600 mr-4">
              ⏳ Awaiting approval (Msg: {pendingApproval.messageId})
            </span>
          )}
          <span className="text-sm text-gray-500">
            💡 Ask database questions to see the approval workflow
          </span>
        </div>
      </div>
    </div>
  );
};

export default ChatWithApproval;
