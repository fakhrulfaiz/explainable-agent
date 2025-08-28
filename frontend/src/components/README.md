# Chat Components

This directory contains modular, TypeScript-based chat components that can be easily reused across different parts of your application.

## Components

### ChatComponent

The main chat interface component with support for:

- Message history
- Approval/disapproval workflow
- Feedback forms
- Loading states
- Error handling

### Message

Individual message display component that handles:

- User vs assistant message styling
- Approval status indicators
- Timestamps
- Feedback labels

### FeedbackForm

A form component for collecting user feedback on assistant responses.

### LoadingIndicator

A simple animated loading indicator for when the assistant is typing.

## Usage

```tsx
import { ChatComponent } from "./components";
import { Message } from "./types/chat";

// Basic usage
<ChatComponent
  onSendMessage={async (message, history) => {
    // Your backend integration here
    const response = await fetch("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    });
    return response.text();
  }}
  onApprove={(content, message) => {
    // Handle message approval
    console.log("Approved:", content);
  }}
  onDisapprove={(content, message) => {
    // Handle message disapproval
    console.log("Disapproved:", content);
  }}
  placeholder="Type your message..."
  showApprovalButtons={true}
  className="h-96"
/>;
```

## Props

### ChatComponent Props

| Prop                  | Type                                                       | Required | Description                                  |
| --------------------- | ---------------------------------------------------------- | -------- | -------------------------------------------- |
| `onSendMessage`       | `(message: string, history: Message[]) => Promise<string>` | Yes      | Function to handle sending messages          |
| `onApprove`           | `(content: string, message: Message) => Promise<void>`     | No       | Function to handle message approval          |
| `onDisapprove`        | `(content: string, message: Message) => Promise<void>`     | No       | Function to handle message disapproval       |
| `className`           | `string`                                                   | No       | Additional CSS classes                       |
| `placeholder`         | `string`                                                   | No       | Input placeholder text                       |
| `showApprovalButtons` | `boolean`                                                  | No       | Whether to show approval/disapproval buttons |
| `disabled`            | `boolean`                                                  | No       | Whether the chat is disabled                 |

## Types

All TypeScript interfaces are defined in `../types/chat.ts`:

- `Message`: Interface for chat messages
- `ChatComponentProps`: Props for the main chat component
- `MessageComponentProps`: Props for individual messages
- `FeedbackFormProps`: Props for the feedback form

## Styling

Components use Tailwind CSS classes for styling. Make sure Tailwind is properly configured in your project.

## Features

- **TypeScript Support**: Full type safety
- **Modular Design**: Each component has a single responsibility
- **Approval Workflow**: Built-in support for message approval/disapproval
- **Feedback System**: Users can provide feedback to improve responses
- **Error Handling**: Graceful error display
- **Loading States**: Visual feedback during API calls
- **Responsive Design**: Works on all screen sizes
