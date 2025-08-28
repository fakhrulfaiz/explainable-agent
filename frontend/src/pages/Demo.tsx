import React, { useState } from 'react';
import { ChatComponent } from '../components';
import { Message } from '../types/chat';

const Demo: React.FC = () => {
  const [chatKey, setChatKey] = useState<number>(0); // For resetting chat

  // Mock responses for demo
  const mockResponses: string[] = [
    "I understand your question. Let me provide a detailed explanation with examples and practical insights.",
    "That's a great point! Here's my analysis based on the information provided.",
    "I can help you with that. Let me break this down step by step for better understanding.",
    "Based on my analysis, here are the key points you should consider.",
    "Let me provide some context and explain the reasoning behind this approach."
  ];

  // Handle sending messages - this is where you'd integrate with your backend
  const handleSendMessage = async (message: string, messageHistory: Message[]): Promise<string> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));
    
    // Mock different responses based on message content
    if (message.toLowerCase().includes('error')) {
      throw new Error('Simulated error for testing');
    }

    // Return a mock response
    const randomResponse = mockResponses[Math.floor(Math.random() * mockResponses.length)];
    return `${randomResponse}\n\nYou asked: "${message}"\n\nThis response demonstrates how the chat component works with approval functionality.`;
  };

  // Handle approval
  const handleApprove = async (content: string, message: Message): Promise<void> => {
    console.log('Approved message:', { content, message });
    // Here you could send approval to your backend
  };

  // Handle disapproval
  const handleDisapprove = async (content: string, message: Message): Promise<void> => {
    console.log('Disapproved message:', { content, message });
    // Here you could send disapproval to your backend
  };

  return (
    <div className="h-screen bg-gray-50 p-4 overflow-hidden">
      <div className="max-w-4xl mx-auto h-full flex flex-col">
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Reusable Chat Component Demo
          </h1>
          <p className="text-gray-600">
            A flexible chat interface with approval functionality
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
          {/* Main Chat */}
          <div className="bg-white rounded-lg shadow-sm flex flex-col">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">Chat with Approval</h2>
              <p className="text-sm text-gray-600">Messages require approval/disapproval</p>
            </div>
            <div className="flex-1 min-h-0">
              <ChatComponent
                key={`chat-approval-${chatKey}`}
                onSendMessage={handleSendMessage}
                onApprove={handleApprove}
                onDisapprove={handleDisapprove}
                placeholder="Ask me anything..."
                showApprovalButtons={true}
                className="h-full"
              />
            </div>
          </div>

          {/* Simple Chat */}
          <div className="bg-white rounded-lg shadow-sm flex flex-col">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">Simple Chat</h2>
              <p className="text-sm text-gray-600">No approval needed</p>
            </div>
            <div className="flex-1 min-h-0">
              <ChatComponent
                key={`chat-simple-${chatKey}`}
                onSendMessage={handleSendMessage}
                placeholder="Just chat..."
                showApprovalButtons={false}
                className="h-full"
              />
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="mt-6 text-center">
          <button
            onClick={() => setChatKey(prev => prev + 1)}
            className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Reset Both Chats
          </button>
        </div>

        {/* Usage Example */}
        <div className="mt-8 bg-gray-900 text-gray-100 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-3">Usage Example:</h3>
          <pre className="text-sm overflow-x-auto">
{`// Import the component
import { ChatComponent } from './components';

// Basic usage
<ChatComponent
  onSendMessage={async (message, history) => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, history })
    });
    return response.text();
  }}
  onApprove={(content, message) => {
    console.log('User approved:', content);
  }}
  onDisapprove={(content, message) => {
    console.log('User disapproved:', content);
  }}
  placeholder="Ask me anything..."
  showApprovalButtons={true}
  className="h-96"
/>`}
          </pre>
        </div>

        <div className="mt-4 text-center text-sm text-gray-500">
          💡 Try typing "error" to see error handling, or any other message for normal responses
        </div>
      </div>
    </div>
  );
};

export default Demo;
