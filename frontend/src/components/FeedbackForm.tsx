import React, { useRef, useEffect } from 'react';
import { FeedbackFormProps } from '../types/chat';

const FeedbackForm: React.FC<FeedbackFormProps> = ({
  feedbackText,
  setFeedbackText,
  onSendFeedback,
  onCancel,
  isLoading
}) => {
  const formRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll and focus when form mounts
  useEffect(() => {
    if (formRef.current) {
      // Scroll the form into view, centering it in the viewport
      formRef.current.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center',
        inline: 'nearest'
      });
    }
    // Focus textarea after scroll animation completes
    const timer = setTimeout(() => {
      textareaRef.current?.focus();
    }, 400);

    return () => clearTimeout(timer);
  }, []);

  return (
    <div ref={formRef} className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
      <div className="mb-3">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Please provide feedback to improve the response:
        </label>
        <textarea
          ref={textareaRef}
          value={feedbackText}
          onChange={(e) => setFeedbackText(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical text-gray-900 bg-white"
          placeholder="Your feedback..."
        />
      </div>
      <div className="flex gap-2">
        <button
          onClick={onSendFeedback}
          disabled={!feedbackText.trim() || isLoading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          Send Feedback
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 text-gray-700 bg-gray-100 border border-gray-300 rounded-lg hover:bg-gray-200 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
};

export default FeedbackForm;
