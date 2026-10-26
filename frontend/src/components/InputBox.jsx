/**
 * InputBox component - user message input area.
 * 
 * Props:
 *   - onSend: (message: string) => void - callback when user clicks send
 *   - isLoading: boolean - disable input while waiting for response
 */

import { useState, useRef, useEffect } from 'react'

export function InputBox({ onSend, isLoading }) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef(null)

  // Auto-expand textarea as user types
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px'
    }
  }, [message])

  const handleSend = () => {
    if (message.trim() && !isLoading) {
      onSend(message.trim())
      setMessage('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="input-area">
      <div className="input-wrapper">
        <textarea
          ref={textareaRef}
          className="input-field"
          placeholder="Type a message... (Shift+Enter for new line)"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows="1"
        />
      </div>
      <button
        className="send-btn"
        onClick={handleSend}
        disabled={isLoading || !message.trim()}
        title="Send message (Enter)"
      >
        ➤
      </button>
    </div>
  )
}
