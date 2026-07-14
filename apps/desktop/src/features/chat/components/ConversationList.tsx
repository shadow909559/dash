import { Conversation } from '../types';
import './chat.css';

export function ConversationList({
  conversations,
  activeConversationId,
  onSelect,
}: {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="chat__convList" role="list">
      {conversations.length === 0 ? (
        <div className="chat__empty">No conversations yet.</div>
      ) : null}

      {conversations.map((c) => {
        const active = c.id === activeConversationId;
        return (
          <button
            key={c.id}
            className={`chat__convItem ${active ? 'chat__convItem--active' : ''}`}
            onClick={() => onSelect(c.id)}
            type="button"
          >
            <div className="chat__convTitle">{c.title}</div>
          </button>
        );
      })}
    </div>
  );
}

