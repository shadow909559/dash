import { ChatMessage } from '../types';
import { MarkdownMessage } from './MarkdownMessage';
import './chat.css';

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`chat__bubbleRow ${isUser ? 'chat__bubbleRow--user' : 'chat__bubbleRow--assistant'}`}>
      <div className={`chat__bubble ${isUser ? 'chat__bubble--user' : 'chat__bubble--assistant'}`}>
        <div className="chat__bubbleContent">
          <MarkdownMessage content={message.content} />
        </div>

        {message.attachments && message.attachments.length > 0 ? (
          <div className="chat__attachments" aria-label="Attachments">
            {message.attachments.map((a) => (
              <div key={a.name} className="chat__attachment">
                📎 {a.name}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

