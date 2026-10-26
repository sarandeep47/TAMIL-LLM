/**
 * Sidebar component - conversation history and new chat button.
 * 
 * Props:
 *   - conversations: Array<{id, title, timestamp}> - list of past conversations
 *   - activeConversationId: string - currently selected conversation
 *   - onNewChat: () => void - create new conversation
 *   - onSelectConversation: (id: string) => void - select conversation
 */

export function Sidebar({
  conversations = [],
  activeConversationId = null,
  onNewChat,
  onSelectConversation,
}) {
  return (
    <div className="sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        + New chat
      </button>

      <div className="conversation-list">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`conversation-item ${conv.id === activeConversationId ? 'active' : ''}`}
            onClick={() => onSelectConversation(conv.id)}
            title={conv.title}
          >
            {conv.title}
          </div>
        ))}
      </div>
    </div>
  )
}
