import React, { useState } from 'react';
import { ChatComponent } from '../components';
import { Message } from '../types/chat';

const SimpleChat: React.FC = () => {
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
    return `${randomResponse}\n\nYou asked: "${message}"\n\nThis is a simple chat without approval functionality.`;
  };

  return (
    <div className="h-screen bg-gray-50 p-4 overflow-hidden">
      <div className="max-w-4xl mx-auto h-full flex flex-col">
        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Simple Chat
          </h1>
          <p className="text-gray-600">
            Basic chat interface without approval workflow
          </p>
        </div>

        {/* Chat Container */}
        <div className="flex-1 min-h-0">
          <div className="bg-white rounded-lg shadow-sm h-full flex flex-col">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">Simple Chat</h2>
              <p className="text-sm text-gray-600">Direct conversation without approval requirements</p>
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
        <div className="mt-4 text-center">
          <button
            onClick={() => setChatKey(prev => prev + 1)}
            className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors mr-4"
          >
            Reset Chat
          </button>
          <span className="text-sm text-gray-500">
            💡 Try typing "error" to see error handling
          </span>
        </div>
      </div>
    </div>
  );
};

export default SimpleChat;
