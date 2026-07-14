export type ChatRole = 'user' | 'assistant';

export type ChatAttachment = {
  name: string;
};

export type MessageStatus = 'sending' | 'sent' | 'streaming' | 'complete' | 'error';

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
  attachments?: ChatAttachment[];
  status?: MessageStatus;
};

export type Conversation = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt?: number;
  messageCount?: number;
};