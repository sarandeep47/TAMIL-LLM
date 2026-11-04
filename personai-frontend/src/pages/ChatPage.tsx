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
import type { Message } from '../types/chat';

export const ChatPage: React.FC = () => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [transcribedText, setTranscribedText] = useState('');
  const [userName] = useState('User');

  const {
    currentConversationId,
    isLoading,
    error,
    createConversation,
    addMessage,
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
  }, []);

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || !currentConversationId || isLoading) return;

    try {
      setError(null);

      // Add user message
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      };
      addMessage(userMessage);

      // Add loading message
      const loadingMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      };
      addMessage(loadingMessage);
      setLoading(true);

      // Send text to backend LLM using POST /api/chat
      const response = await fetch('http://localhost:8000/api/chat', {
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

      // Remove loading message
      const currentConv = getCurrentConversation();
      if (currentConv) {
        currentConv.messages = currentConv.messages.filter(m => !m.isLoading);
      }

      // Add AI response
      const aiMessage: Message = {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: data.bot_text || 'No response',
        timestamp: new Date(),
        llmLatency: data.llm_latency_ms,
      };
      addMessage(aiMessage);

      // Play response audio
      if (data.bot_text) {
        try {
          await voiceService.playText(data.bot_text, 0.7);
        } catch (ttsErr) {
          console.warn('TTS failed:', ttsErr);
        }
      }
    } catch (err) {
      console.error('Send message error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);

      // Remove loading message
      const currentConv = getCurrentConversation();
      if (currentConv) {
        currentConv.messages = currentConv.messages.filter(m => !m.isLoading);
      }
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

      // Stop recording and get audio blob
      const audioBlob = await voiceService.stopRecording();

      // Send to backend
      const response = await apiClient.voiceTurn(audioBlob);

      if (!currentConversationId) {
        setError('No conversation active');
        return;
      }

      // Add user message with STT result
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
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.bot_text,
          timestamp: new Date(),
          llmLatency: response.llm_latency_ms,
        };
        addMessage(aiMessage);

        // Play response audio
        await voiceService.playText(response.bot_text, 0.7);
      } else {
        setError('No speech detected. Please try again.');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process voice';
      setVoiceError(errorMessage);
    } finally {
      setLoading(false);
      setTimeout(() => setTranscribedText(''), 3000);
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
                <ChatMessage key={message.id} message={message} />
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
