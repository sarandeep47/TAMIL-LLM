import { create } from 'zustand';
import type { Message, Conversation } from '../types/chat';

interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  createConversation: () => void;
  selectConversation: (id: string) => void;
  addMessage: (message: Message) => void;
  deleteConversation: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  getCurrentConversation: () => Conversation | null;
  getConversationTitle: (id: string) => string;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  isLoading: false,
  error: null,

  createConversation: () => {
    const newConversation: Conversation = {
      id: Date.now().toString(),
      title: 'New Conversation',
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    set((state) => ({
      conversations: [newConversation, ...state.conversations],
      currentConversationId: newConversation.id,
    }));
  },

  selectConversation: (id: string) => {
    set({ currentConversationId: id });
  },

  addMessage: (message: Message) => {
    set((state) => {
      const conversations = state.conversations.map((conv) => {
        if (conv.id === state.currentConversationId) {
          // Update title if it's the first message
          const title =
            conv.messages.length === 0
              ? message.content.substring(0, 50) + (message.content.length > 50 ? '...' : '')
              : conv.title;

          return {
            ...conv,
            messages: [...conv.messages, message],
            title,
            updatedAt: new Date(),
          };
        }
        return conv;
      });

      return { conversations };
    });
  },

  deleteConversation: (id: string) => {
    set((state) => {
      const filtered = state.conversations.filter((c) => c.id !== id);
      return {
        conversations: filtered,
        currentConversationId:
          state.currentConversationId === id ? (filtered.length > 0 ? filtered[0].id : null) : state.currentConversationId,
      };
    });
  },

  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },

  setError: (error: string | null) => {
    set({ error });
  },

  getCurrentConversation: () => {
    const state = get();
    return state.conversations.find((c) => c.id === state.currentConversationId) || null;
  },

  getConversationTitle: (id: string) => {
    const state = get();
    const conv = state.conversations.find((c) => c.id === id);
    return conv?.title || 'Unknown';
  },
}));
