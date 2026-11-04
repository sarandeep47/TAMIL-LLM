export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sttLatency?: number;
  llmLatency?: number;
  isLoading?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface VoiceResponseData {
  user_text: string;
  bot_text: string;
  stt_latency_ms: number;
  llm_latency_ms: number;
}

export interface HealthStatus {
  ollama: boolean;
  whisper: boolean;
}

export interface User {
  id: string;
  name: string;
  email?: string;
  preferences?: {
    language: 'ta' | 'en';
    theme: 'dark' | 'light';
    voiceEnabled: boolean;
    ttsSpeed: number;
  };
}

export interface SuggestionCard {
  id: string;
  icon: string;
  title: string;
  description: string;
  action: () => void;
}
