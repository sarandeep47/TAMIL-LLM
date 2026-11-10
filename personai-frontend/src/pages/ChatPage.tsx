import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, Mic2, Zap, Calendar } from 'lucide-react';
import { Sidebar } from '../components/Sidebar';
import { ChatMessage } from '../components/ChatMessage';
import { MessageComposer } from '../components/MessageComposer';
import { VoiceVisualizer } from '../components/VoiceVisualizer';
import { WelcomeScreen } from '../components/WelcomeScreen';
import { useChatStore } from '../store/chatStore';
import { apiClient } from '../services/api';
import { voiceService } from '../services/voiceService';
import { streamChat, streamVoiceTurn, type StreamHandlers } from '../streamClient';
import { API_BASE } from '../constants';
import type { Message } from '../types/chat';
import type { SSEEvent } from '../sse';

export const ChatPage: React.FC = () => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [transcribedText, setTranscribedText] = useState('');
  const [userName] = useState('User');
  const [streamMetrics, setStreamMetrics] = useState<Record<string, unknown> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const clientStartTimeRef = useRef<number>(0);
  const firstEventTimeRef = useRef<number>(0);
  const firstSentenceTimeRef = useRef<number>(0);

  const useStreaming = import.meta.env.VITE_STREAMING !== '0';

  const {
    currentConversationId,
    isLoading,
    error,
    createConversation,
    addMessage,
    updateMessage,
    setLoading,
    setError,
    getCurrentConversation,
  } = useChatStore();

  const currentConversation = getCurrentConversation();
  const isWelcomeScreen = !currentConversationId || currentConversation?.messages.length === 0;

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentConversation?.messages]);

  // Initialize first conversation
  useEffect(() => {
    if (!currentConversationId) {
      createConversation();
    }

    // Cleanup on unmount: abort any pending requests
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || !currentConversationId || isLoading) return;

    try {
      setError(null);
      setStreamMetrics(null);
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      // Add user message
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      };
      addMessage(userMessage);

      // Add assistant placeholder
      const assistantId = (Date.now() + 1).toString();
      const assistantMessage: Message = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      };
      addMessage(assistantMessage);
      setLoading(true);

      clientStartTimeRef.current = Date.now();
      firstEventTimeRef.current = 0;
      firstSentenceTimeRef.current = 0;

      if (useStreaming) {
        try {
          let gotFirstEvent = false;

          const handlers: StreamHandlers = {
            onEvent: (event: SSEEvent) => {
              if (!gotFirstEvent) {
                firstEventTimeRef.current = Date.now();
                gotFirstEvent = true;
              }

              switch (event.event) {
                case 'token':
                  updateMessage(currentConversationId, assistantId, (msg) => ({
                    ...msg,
                    content: msg.content + event.text,
                    isLoading: false,
                  }));
                  break;

                case 'sentence':
                  updateMessage(currentConversationId, assistantId, (msg) => {
                    if (!msg.content && event.index === 0) {
                      if (!firstSentenceTimeRef.current) {
                        firstSentenceTimeRef.current = Date.now();
                      }
                      return {
                        ...msg,
                        content: event.text,
                        isLoading: false,
                      };
                    }
                    return msg;
                  });
                  break;

                case 'done':
                  if (!firstSentenceTimeRef.current) {
                    firstSentenceTimeRef.current = Date.now();
                  }
                  updateMessage(currentConversationId, assistantId, (msg) => ({
                    ...msg,
                    content: event.reply,
                    isLoading: false,
                  }));
                  setStreamMetrics(event);
                  if (event.reply) {
                    try {
                      voiceService.playText(event.reply, 0.7).catch(() => {});
                    } catch {}
                  }
                  break;

                case 'error':
                  updateMessage(currentConversationId, assistantId, (msg) => ({
                    ...msg,
                    content: `Error: ${event.message}`,
                    isLoading: false,
                  }));
                  setError(event.message);
                  break;
              }
            },

            onError: (message: string) => {
              if (!gotFirstEvent) {
                console.warn('Streaming failed, using fallback:', message);
                fallbackToNonStreaming(text, assistantId);
              } else {
                updateMessage(currentConversationId, assistantId, (msg) => ({
                  ...msg,
                  content: `Error: ${message}`,
                  isLoading: false,
                }));
                setError(message);
              }
            },

            onComplete: () => {},
          };

          await streamChat(text, handlers, abortControllerRef.current.signal);
          setLoading(false);
        } catch (err) {
          console.error('Streaming error:', err);
          if (!(err instanceof DOMException && err.name === 'AbortError')) {
            fallbackToNonStreaming(text, assistantId);
          }
        }
      } else {
        fallbackToNonStreaming(text, assistantId);
      }
    } catch (err) {
      console.error('Send message error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);
      setLoading(false);
    }
  };

  const fallbackToNonStreaming = async (text: string, assistantId: string) => {
    try {
      // Use non-streaming endpoint
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: text.trim() }),
      });

      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }

      const data = await response.json();

      updateMessage(currentConversationId!, assistantId, (msg) => ({
        ...msg,
        content: data.bot_text || 'No response',
        isLoading: false,
        llmLatency: data.llm_latency_ms,
      }));

      // Play response audio
      if (data.bot_text) {
        try {
          await voiceService.playText(data.bot_text, 0.7);
        } catch (ttsErr) {
          console.warn('TTS failed:', ttsErr);
        }
      }

      setStreamMetrics({
        event: 'done',
        reply: data.bot_text,
        ttft_ms: firstEventTimeRef.current ? Date.now() - clientStartTimeRef.current : 0,
        first_sentence_ms: Date.now() - clientStartTimeRef.current,
        total_ms: Date.now() - clientStartTimeRef.current,
        route: data.route || 'fallback',
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);
      updateMessage(currentConversationId!, assistantId, (msg) => ({
        ...msg,
        isLoading: false,
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceStart = async () => {
    try {
      setVoiceError(null);
      setTranscribedText('');
      await voiceService.startRecording();
      setIsVoiceActive(true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start recording';
      setVoiceError(errorMessage);
    }
  };

  const handleVoiceEnd = async () => {
    try {
      setIsVoiceActive(false);
      setLoading(true);
      setStreamMetrics(null);
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      // Stop recording and get audio blob
      const audioBlob = await voiceService.stopRecording();

      if (!currentConversationId) {
        setError('No conversation active');
        return;
      }

      clientStartTimeRef.current = Date.now();
      firstEventTimeRef.current = 0;
      firstSentenceTimeRef.current = 0;

      const assistantId = (Date.now() + 2).toString();

      if (useStreaming) {
        try {
          let gotFirstEvent = false;
          let assistantBubbleCreated = false;

          const handlers: StreamHandlers = {
            onEvent: (event: SSEEvent) => {
              if (!gotFirstEvent) {
                firstEventTimeRef.current = Date.now();
                gotFirstEvent = true;
              }

              switch (event.event) {
                case 'stt':
                  // Add user message with transcript
                  setTranscribedText(event.user_text);
                  if (event.user_text) {
                    const userMsg: Message = {
                      id: Date.now().toString(),
                      role: 'user',
                      content: event.user_text,
                      timestamp: new Date(),
                      sttLatency: event.stt_latency_ms,
                    };
                    addMessage(userMsg);
                  }
                  break;

                case 'meta':
                  // Create assistant bubble on first non-stt event if not created
                  if (!assistantBubbleCreated) {
                    const assistantMessage: Message = {
                      id: assistantId,
                      role: 'assistant',
                      content: '',
                      timestamp: new Date(),
                      isLoading: true,
                    };
                    addMessage(assistantMessage);
                    assistantBubbleCreated = true;
                  }
                  break;

                case 'token':
                  // Create assistant bubble on first token if not created
                  if (!assistantBubbleCreated) {
                    const assistantMessage: Message = {
                      id: assistantId,
                      role: 'assistant',
                      content: '',
                      timestamp: new Date(),
                      isLoading: true,
                    };
                    addMessage(assistantMessage);
                    assistantBubbleCreated = true;
                  }
                  updateMessage(currentConversationId, assistantId, (msg) => ({
                    ...msg,
                    content: msg.content + event.text,
                    isLoading: false,
                  }));
                  break;

                case 'sentence':
                  // Create assistant bubble on first sentence if not created
                  if (!assistantBubbleCreated) {
                    const assistantMessage: Message = {
                      id: assistantId,
                      role: 'assistant',
                      content: '',
                      timestamp: new Date(),
                      isLoading: true,
                    };
                    addMessage(assistantMessage);
                    assistantBubbleCreated = true;
                  }
                  updateMessage(currentConversationId, assistantId, (msg) => {
                    if (!msg.content && event.index === 0) {
                      if (!firstSentenceTimeRef.current) {
                        firstSentenceTimeRef.current = Date.now();
                      }
                      return {
                        ...msg,
                        content: event.text,
                        isLoading: false,
                      };
                    }
                    return msg;
                  });
                  break;

                case 'done':
                  // Create assistant bubble if not created and show done.reply
                  if (!assistantBubbleCreated) {
                    const assistantMessage: Message = {
                      id: assistantId,
                      role: 'assistant',
                      content: event.reply,
                      timestamp: new Date(),
                      isLoading: false,
                    };
                    addMessage(assistantMessage);
                    assistantBubbleCreated = true;
                  } else {
                    updateMessage(currentConversationId, assistantId, (msg) => ({
                      ...msg,
                      content: event.reply,
                      isLoading: false,
                    }));
                  }
                  if (!firstSentenceTimeRef.current) {
                    firstSentenceTimeRef.current = Date.now();
                  }
                  setStreamMetrics(event);
                  if (event.reply) {
                    try {
                      voiceService.playText(event.reply, 0.7).catch(() => {});
                    } catch {}
                  }
                  break;

                case 'error':
                  if (!assistantBubbleCreated) {
                    const assistantMessage: Message = {
                      id: assistantId,
                      role: 'assistant',
                      content: `Error: ${event.message}`,
                      timestamp: new Date(),
                      isLoading: false,
                    };
                    addMessage(assistantMessage);
                    assistantBubbleCreated = true;
                  } else {
                    updateMessage(currentConversationId, assistantId, (msg) => ({
                      ...msg,
                      content: `Error: ${event.message}`,
                      isLoading: false,
                    }));
                  }
                  setError(event.message);
                  break;
              }
            },

            onError: (message: string) => {
              if (!gotFirstEvent) {
                console.warn('Voice streaming failed, using fallback:', message);
                fallbackVoiceTurn(audioBlob, assistantId);
              } else {
                if (!assistantBubbleCreated) {
                  const assistantMessage: Message = {
                    id: assistantId,
                    role: 'assistant',
                    content: `Error: ${message}`,
                    timestamp: new Date(),
                    isLoading: false,
                  };
                  addMessage(assistantMessage);
                } else {
                  updateMessage(currentConversationId, assistantId, (msg) => ({
                    ...msg,
                    content: `Error: ${message}`,
                    isLoading: false,
                  }));
                }
                setError(message);
              }
            },

            onComplete: () => {},
          };

          await streamVoiceTurn(audioBlob, handlers, abortControllerRef.current.signal);
          setLoading(false);
        } catch (err) {
          console.error('Voice streaming error:', err);
          if (!(err instanceof DOMException && err.name === 'AbortError')) {
            fallbackVoiceTurn(audioBlob, assistantId);
          }
        }
      } else {
        fallbackVoiceTurn(audioBlob, assistantId);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process voice';
      setVoiceError(errorMessage);
      setLoading(false);
    } finally {
      setTimeout(() => setTranscribedText(''), 3000);
    }
  };

  const fallbackVoiceTurn = async (audioBlob: Blob, assistantId: string) => {
    try {
      const response = await apiClient.voiceTurn(audioBlob);

      if (response.user_text) {
        setTranscribedText(response.user_text);
        const userMessage: Message = {
          id: Date.now().toString(),
          role: 'user',
          content: response.user_text,
          timestamp: new Date(),
          sttLatency: response.stt_latency_ms,
        };
        addMessage(userMessage);

        // Add AI response
        const aiMessage: Message = {
          id: assistantId,
          role: 'assistant',
          content: response.bot_text,
          timestamp: new Date(),
          llmLatency: response.llm_latency_ms,
        };
        addMessage(aiMessage);

        // Play response audio
        await voiceService.playText(response.bot_text, 0.7);

        setStreamMetrics({
          event: 'done',
          reply: response.bot_text,
          ttft_ms: Date.now() - clientStartTimeRef.current,
          first_sentence_ms: Date.now() - clientStartTimeRef.current,
          total_ms: Date.now() - clientStartTimeRef.current,
          route: 'fallback',
        });
      } else {
        setError('No speech detected. Please try again.');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process voice';
      setVoiceError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const suggestionCards = [
    {
      icon: <MessageCircle className="w-6 h-6 text-accent-purple" />,
      title: 'Ask anything',
      description: 'Get answers, ideas, or explanations.',
      onClick: () => handleSendMessage('Can you help me with something?'),
    },
    {
      icon: <Mic2 className="w-6 h-6 text-accent-purple" />,
      title: 'Talk with me',
      description: 'Use your voice to chat naturally.',
      onClick: handleVoiceStart,
    },
    {
      icon: <Zap className="w-6 h-6 text-accent-purple" />,
      title: 'Summarize',
      description: 'Turn long content into key points.',
      onClick: () => handleSendMessage('Can you summarize this for me?'),
    },
    {
      icon: <Calendar className="w-6 h-6 text-accent-purple" />,
      title: 'Plan & Organize',
      description: 'Tasks, schedules, and daily planning.',
      onClick: () => handleSendMessage('Help me organize my day'),
    },
  ];

  return (
    <div className="flex h-screen bg-dark-bg text-dark-text">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col md:ml-64 overflow-hidden">
        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto">
          {isWelcomeScreen ? (
            <WelcomeScreen userName={userName} suggestions={suggestionCards} />
          ) : (
            <div className="p-6 max-w-4xl mx-auto">
              {error && (
                <div className="mb-6 p-4 bg-red-900/20 border border-red-500/50 text-red-400 rounded-lg">
                  {error}
                </div>
              )}

              {/* Messages */}
              {currentConversation?.messages.map((message) => (
                <div key={message.id}>
                  <ChatMessage message={message} />
                  {/* Debug line for assistant messages */}
                  {!message.isLoading && message.role === 'assistant' && streamMetrics && new URLSearchParams(window.location.search).get('debug') === '1' && (
                    <div className="text-xs text-dark-text-muted ml-12 mt-1 font-mono">
                      route={String(streamMetrics.route ?? 'N/A')} | client_ttft={(firstEventTimeRef.current ? firstEventTimeRef.current - clientStartTimeRef.current : 0)}ms | client_sentence={(firstSentenceTimeRef.current ? firstSentenceTimeRef.current - clientStartTimeRef.current : 0)}ms | client_done={(Date.now() - clientStartTimeRef.current)}ms | server_ttft={String(streamMetrics.ttft_ms ?? 'N/A')}ms | server_sentence={String(streamMetrics.first_sentence_ms ?? 'N/A')}ms | server_total={String(streamMetrics.total_ms ?? 'N/A')}ms | prefill={String(streamMetrics.prefill_ms ?? 'N/A')}ms
                    </div>
                  )}
                </div>
              ))}

              {/* Voice Visualizer */}
              {(isVoiceActive || isLoading) && <VoiceVisualizer isActive={isVoiceActive} transcribedText={transcribedText} isProcessing={isLoading && !isVoiceActive} />}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Message Composer */}
        <MessageComposer
          onSendMessage={handleSendMessage}
          onVoiceStart={handleVoiceStart}
          onVoiceEnd={handleVoiceEnd}
          isLoading={isLoading}
          isVoiceActive={isVoiceActive}
          voiceError={voiceError}
        />
      </div>
    </div>
  );
};

