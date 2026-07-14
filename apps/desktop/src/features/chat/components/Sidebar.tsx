import './chat.css';
import { ConversationList } from './ConversationList';
import { Conversation } from '../types';
import { AgentBadge } from '../../agent/AgentBadge';
import { MachineInfoPanel } from '../../agent/MachineInfoPanel';

export function Sidebar({
  conversations,
  activeConversationId,
  onNewConversation,
  onSelectConversation,
}: {
  conversations: Conversation[];
  activeConversationId: string | null;
  onNewConversation: () => void;
  onSelectConversation: (id: string) => void;
}) {
  return (
    <aside className="chat__sidebar">
      <div className="chat__sidebarHeader">
        <div className="chat__brand">DASH</div>
        <button className="chat__newButton" onClick={onNewConversation} type="button">
          + New
        </button>
      </div>

      <div className="chat__sidebarDivider" />
      <ConversationList
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={onSelectConversation}
      />

      {/* Agent connection badge at the bottom of sidebar */}
      <div style={{ marginTop: 'auto', padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
        <AgentBadge />
      </div>
      <MachineInfoPanel />
    </aside>
  );
}

