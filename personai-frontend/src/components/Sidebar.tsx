import React, { useState } from 'react';
import { Menu, X, Plus, MessageCircle, Settings, History, Trash2, LogOut } from 'lucide-react';
import { useChatStore } from '../store/chatStore';

export const Sidebar: React.FC = () => {
  const [isOpen, setIsOpen] = useState(true);
  const { conversations, currentConversationId, createConversation, selectConversation, deleteConversation } = useChatStore();

  const handleNewChat = () => {
    createConversation();
    setIsOpen(true);
  };

  return (
    <>
      {/* Mobile Menu Button */}
      <button
        className="fixed top-4 left-4 z-50 md:hidden bg-dark-card hover:bg-dark-border text-accent-purple p-2 rounded-lg transition"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Sidebar */}
      <div
        className={`fixed left-0 top-0 h-screen w-64 bg-gradient-to-b from-dark-bg to-dark-card border-r border-dark-border transition-transform duration-300 transform z-40 ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="flex flex-col h-full p-4">
          {/* Header */}
          <div className="flex items-center gap-3 mb-8 pt-4">
            <div className="w-10 h-10 bg-accent-purple rounded-lg flex items-center justify-center font-bold text-white">
              P
            </div>
            <div>
              <h1 className="font-bold text-white text-lg">PersonAI</h1>
              <p className="text-xs text-dark-text-muted">Assistant</p>
            </div>
          </div>

          {/* New Chat Button */}
          <button
            onClick={handleNewChat}
            className="w-full bg-accent-purple hover:bg-accent-purple-dark text-white font-medium py-2 px-4 rounded-lg mb-6 flex items-center justify-center gap-2 transition transform hover:scale-105"
          >
            <Plus size={18} />
            New Chat
          </button>

          {/* Navigation Menu */}
          <nav className="flex-1 space-y-2 mb-6 overflow-y-auto">
            {/* Chat History */}
            <div>
              <div className="flex items-center gap-2 text-dark-text-muted text-sm font-semibold px-3 py-2 mb-2">
                <History size={16} />
                Conversation History
              </div>
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {conversations.length === 0 ? (
                  <p className="text-xs text-dark-text-muted px-3 py-2 italic">No conversations yet</p>
                ) : (
                  conversations.map((conv) => (
                    <div
                      key={conv.id}
                      className="group relative"
                    >
                      <button
                        onClick={() => {
                          selectConversation(conv.id);
                          setIsOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 rounded-lg transition truncate ${
                          currentConversationId === conv.id
                            ? 'bg-accent-purple text-white'
                            : 'text-dark-text-muted hover:bg-dark-border'
                        }`}
                      >
                        <MessageCircle size={14} className="inline mr-2" />
                        {conv.title}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conv.id);
                        }}
                        className="absolute right-2 top-1/2 transform -translate-y-1/2 opacity-0 group-hover:opacity-100 bg-dark-border hover:bg-red-600 text-dark-text p-1 rounded transition"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </nav>

          {/* Footer */}
          <div className="space-y-2 border-t border-dark-border pt-4">
            <button className="w-full text-left px-3 py-2 rounded-lg text-dark-text-muted hover:bg-dark-border transition flex items-center gap-2">
              <Settings size={16} />
              Settings
            </button>
            <button className="w-full text-left px-3 py-2 rounded-lg text-dark-text-muted hover:bg-dark-border transition flex items-center gap-2">
              <LogOut size={16} />
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 md:hidden z-30"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
};
