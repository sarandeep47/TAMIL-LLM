/**
 * ChatMessage component - displays a single message.
 * 
 * Props:
 *   - message: string - the message text
 *   - role: 'user' | 'assistant' - who sent the message
 *   - isLoading: boolean - whether message is still loading
 */

export function ChatMessage({ message, role, isLoading }) {
  return (
    <div className={`message ${role}`}>
      <div className="message-bubble">
        {isLoading ? (
          <div className="loading-spinner" />
        ) : (
          message
        )}
      </div>
    </div>
  )
}
