/**
 * Main App component for TAMIL-LLM web interface.
 * 
 * Features:
 * - ChatGPT-style layout with messages on left, sidebar on right
 * - Send/receive messages via API
 * - Display loading state while waiting for response
 * - Error handling and display
 * - Health status indicator
 * - Conversation history (basic)
 */

import { useState, useEffect, useRef } from 'react'
import { sendMessage, checkHealth } from './api'
import { ChatMessage } from './components/ChatMessage'
import { InputBox } from './components/InputBox'
import { Sidebar } from './components/Sidebar'

function App() {
  // Messages in current conversation
  const [messages, setMessages] = useState([])
  
  // Conversation history (simple list of past messages)
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)

  // Loading/error states
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [healthStatus, setHealthStatus] = useState(null)

  // Auto-scroll to bottom when messages change
  const messagesEndRef = useRef(null)
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Check backend health on mount
  useEffect(() => {
    checkBackendHealth()
    const healthInterval = setInterval(checkBackendHealth, 30000) // Check every 30s
    return () => clearInterval(healthInterval)
  }, [])

  async function checkBackendHealth() {
    try {
      const health = await checkHealth()
      setHealthStatus(health)
    } catch (err) {
      setHealthStatus({ error: true, message: err.message })
    }
  }

  async function handleSendMessage(userMessage) {
    // Clear previous error
    setError(null)

    // Add user message immediately
    const newMessages = [
      ...messages,
      { role: 'user', content: userMessage, id: Date.now() },
      { role: 'assistant', content: '', id: Date.now() + 1, isLoading: true },
    ]
    setMessages(newMessages)
    setIsLoading(true)

    try {
      // Call backend API
      const response = await sendMessage(userMessage)
      
      // Replace loading message with actual response
      const updatedMessages = newMessages.map((msg) => {
        if (msg.isLoading) {
          return {
            ...msg,
            content: response.reply,
            isLoading: false,
            language: response.language,
            extractedFacts: response.extracted_facts,
          }
        }
        return msg
      })
      setMessages(updatedMessages)

      // Update conversation history (simple: use first user message as title)
      if (!activeConversationId) {
        const conversationId = Date.now().toString()
        const title = userMessage.substring(0, 30) + (userMessage.length > 30 ? '...' : '')
        setConversations([
          { id: conversationId, title, timestamp: new Date().toISOString() },
          ...conversations,
        ])
        setActiveConversationId(conversationId)
      }
    } catch (err) {
      // Replace loading message with error
      const updatedMessages = newMessages.map((msg) => {
        if (msg.isLoading) {
          return {
            ...msg,
            isLoading: false,
          }
        }
        return msg
      })
      setMessages(updatedMessages)
      setError(err.message || 'Failed to get response from chatbot')
    } finally {
      setIsLoading(false)
    }
  }

  function handleNewChat() {
    setMessages([])
    setActiveConversationId(null)
    setError(null)
  }

  function handleSelectConversation(conversationId) {
    setActiveConversationId(conversationId)
    // In a real app, would load messages for this conversation from backend
    setMessages([])
  }

  return (
    <div className="app-container">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
      />

      {/* Main chat area */}
      <div className="chat-area">
        {/* Messages */}
        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="empty-state">
              <h1>TAMIL-LLM Chat</h1>
              <p>Start a conversation with your personal AI assistant</p>
            </div>
          ) : (
            <>
              {error && (
                <div className="error-message">
                  ⚠️ {error}
                </div>
              )}
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg.content}
                  role={msg.role}
                  isLoading={msg.isLoading}
                />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input */}
        <InputBox onSend={handleSendMessage} isLoading={isLoading} />

        {/* Health status indicator */}
        {healthStatus && (
          <div
            className={`health-status ${
              healthStatus.ollama_ready ? 'ready' : 'error'
            }`}
          >
            <div className="status-dot" />
            {healthStatus.ollama_ready
              ? 'Ollama ready'
              : 'Ollama unavailable'}
          </div>
        )}
      </div>
    </div>
  )
}

export default App
