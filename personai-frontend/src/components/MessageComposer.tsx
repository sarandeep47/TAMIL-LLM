import React, { useRef, useState, useEffect } from 'react';
import { Send, Mic, Paperclip, Image as ImageIcon, AlertCircle } from 'lucide-react';

interface MessageComposerProps {
  onSendMessage: (text: string) => void;
  onVoiceStart: () => void;
  onVoiceEnd: () => void;
  isLoading: boolean;
  isVoiceActive: boolean;
  voiceError?: string | null;
}

export const MessageComposer: React.FC<MessageComposerProps> = ({
  onSendMessage,
  onVoiceStart,
  onVoiceEnd,
  isLoading,
  isVoiceActive,
  voiceError,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [message, setMessage] = useState('');
  const [rows, setRows] = useState(1);

  const adjustHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${newHeight}px`;
      
      // Calculate approximate rows
      const lineHeight = parseInt(window.getComputedStyle(textareaRef.current).lineHeight);
      const rows = Math.ceil(newHeight / lineHeight);
      setRows(Math.max(1, rows));
    }
  };

  useEffect(() => {
    adjustHeight();
  }, [message]);

  const handleSend = () => {
    if (message.trim() && !isLoading) {
      onSendMessage(message);
      setMessage('');
      setRows(1);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleVoiceClick = async () => {
    if (isVoiceActive) {
      onVoiceEnd();
    } else {
      onVoiceStart();
    }
  };

  return (
    <div className="border-t border-dark-border bg-dark-bg px-4 py-4">
      {/* Error Message */}
      {voiceError && (
        <div className="mb-3 flex items-center gap-2 bg-red-900/20 border border-red-500/50 text-red-400 px-3 py-2 rounded-lg text-sm">
          <AlertCircle size={16} />
          {voiceError}
        </div>
      )}

      {/* Input Area */}
      <div className="flex items-end gap-3">
        {/* Text Input */}
        <div className="flex-1 bg-dark-card border border-dark-border rounded-lg px-4 py-3 focus-within:border-accent-purple transition">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message or use voice input..."
            rows={rows}
            className="w-full bg-transparent text-dark-text placeholder-dark-text-muted resize-none focus:outline-none"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 flex-col">
          {/* Attachment */}
          <button
            className="p-3 bg-dark-card hover:bg-dark-border text-accent-purple rounded-lg transition transform hover:scale-110"
            title="Attach file"
            disabled={isLoading}
          >
            <Paperclip size={18} />
          </button>

          {/* Image */}
          <button
            className="p-3 bg-dark-card hover:bg-dark-border text-accent-purple rounded-lg transition transform hover:scale-110"
            title="Attach image"
            disabled={isLoading}
          >
            <ImageIcon size={18} />
          </button>

          {/* Voice */}
          <button
            onClick={handleVoiceClick}
            className={`p-3 rounded-lg transition transform hover:scale-110 ${
              isVoiceActive
                ? 'bg-red-600 text-white animate-pulse'
                : 'bg-dark-card hover:bg-dark-border text-accent-purple'
            }`}
            title={isVoiceActive ? 'Stop recording' : 'Start voice input'}
            disabled={isLoading && !isVoiceActive}
          >
            <Mic size={18} />
          </button>

          {/* Send */}
          <button
            onClick={handleSend}
            disabled={!message.trim() || isLoading}
            className="p-3 bg-accent-purple hover:bg-accent-purple-dark text-white rounded-lg transition transform hover:scale-110 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Send message"
          >
            <Send size={18} />
          </button>
        </div>
      </div>

      {/* Help Text */}
      <div className="text-xs text-dark-text-muted mt-2">
        <span>Shift + Enter for new line</span>
      </div>
    </div>
  );
};
