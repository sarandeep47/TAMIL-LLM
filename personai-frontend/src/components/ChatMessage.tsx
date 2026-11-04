import React, { useState } from 'react';
import { Copy, RotateCcw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Message } from '../types/chat';

interface ChatMessageProps {
  message: Message;
  onRegenerate?: () => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onRegenerate }) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex gap-4 mb-6 animate-fade-in ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center font-bold text-white ${
          isUser ? 'bg-blue-600' : 'bg-accent-purple'
        }`}
      >
        {isUser ? 'U' : 'A'}
      </div>

      {/* Message Content */}
      <div className={`flex-1 max-w-2xl ${isUser ? 'flex justify-end' : ''}`}>
        <div
          className={`px-4 py-3 rounded-lg ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-none'
              : 'bg-dark-card text-dark-text border border-dark-border rounded-bl-none'
          }`}
        >
          {message.isLoading ? (
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-current rounded-full animate-bounce" />
              <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
              <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
            </div>
          ) : (
            <div className="prose prose-invert max-w-none">
              <ReactMarkdown
                components={{
                  code: ({ inline, className, children }: any) => {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <SyntaxHighlighter
                        language={match[1]}
                        style={oneDark}
                        className="rounded my-2"
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code className="bg-dark-bg px-1.5 py-0.5 rounded text-sm">
                        {children}
                      </code>
                    );
                  },
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc list-inside mb-2">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside mb-2">{children}</ol>,
                  li: ({ children }) => <li className="mb-1">{children}</li>,
                  h1: ({ children }) => <h1 className="text-xl font-bold mb-2">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-lg font-bold mb-2">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-base font-bold mb-2">{children}</h3>,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-accent-purple pl-3 italic mb-2">
                      {children}
                    </blockquote>
                  ),
                  a: ({ href, children }) => (
                    <a href={href} className="text-accent-purple hover:underline" target="_blank" rel="noreferrer">
                      {children}
                    </a>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Latency Info */}
        {!message.isLoading && (message.sttLatency !== undefined || message.llmLatency !== undefined) && (
          <div className={`text-xs text-dark-text-muted mt-2 flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}>
            {message.sttLatency !== undefined && <span>STT: {message.sttLatency}ms</span>}
            {message.llmLatency !== undefined && <span>LLM: {message.llmLatency}ms</span>}
          </div>
        )}

        {/* Actions */}
        {!message.isLoading && !isUser && (
          <div className={`flex gap-2 mt-3 ${isUser ? 'flex-row-reverse' : ''}`}>
            <button
              onClick={handleCopy}
              className="p-2 hover:bg-dark-border rounded transition text-dark-text-muted hover:text-dark-text"
              title="Copy message"
            >
              {copied ? '✓' : <Copy size={16} />}
            </button>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="p-2 hover:bg-dark-border rounded transition text-dark-text-muted hover:text-dark-text"
                title="Regenerate response"
              >
                <RotateCcw size={16} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
