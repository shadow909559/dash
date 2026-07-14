import { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import { useVoiceStore } from '../voiceStore';
import '../chat.css';

export function ChatComposer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (params: { content: string; attachments?: { name: string }[] }) => void;
}) {
  const [content, setContent] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pushToTalkRef = useRef(false);

  const {
    voiceState,
    isSupported,
    error: voiceError,
    init: initVoice,
    startRecording,
    stopRecording,
  } = useVoiceStore();

  const isListening = voiceState === 'listening';
  const isSpeaking = voiceState === 'speaking';

  const trimmed = useMemo(() => content.trim(), [content]);

  // Initialize voice on mount
  useEffect(() => {
    if (isSupported) {
      initVoice();
    }
  }, [isSupported, initVoice]);

  const handleSend = () => {
    if (disabled) return;
    const msg = trimmed;
    if (!msg) return;

    onSend({ content: msg });
    setContent('');
  };

  const handlePickFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const attachments = Array.from(files).map((f) => ({ name: f.name }));
    onSend({ content: trimmed ? trimmed : 'Attached files', attachments });
    setContent('');
  };

  // ── Push-to-talk handlers ────────────────────────────────────────────
  const handleVoicePointerDown = useCallback(async () => {
    if (disabled || isListening || isSpeaking) return;
    pushToTalkRef.current = true;
    await startRecording();
  }, [disabled, isListening, isSpeaking, startRecording]);

  const handleVoicePointerUp = useCallback(() => {
    if (!pushToTalkRef.current) return;
    pushToTalkRef.current = false;
    stopRecording();
  }, [stopRecording]);

  // Keyboard shortcut: hold Space for push-to-talk
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't activate if user is typing in the textarea
      if (e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLInputElement) return;
      if (e.key === ' ' && !e.repeat && !pushToTalkRef.current) {
        e.preventDefault();
        pushToTalkRef.current = true;
        startRecording();
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === ' ' && pushToTalkRef.current) {
        e.preventDefault();
        pushToTalkRef.current = false;
        stopRecording();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [startRecording, stopRecording]);

  return (
    <div className="chat__composer" role="region" aria-label="Message composer">
      <input
        ref={fileInputRef}
        className="chat__fileInput"
        type="file"
        multiple
        onChange={(e) => handlePickFiles(e.target.files)}
      />

      {/* Voice error tooltip */}
      {voiceError ? (
        <div className="chat__voiceError" role="alert">
          {voiceError}
        </div>
      ) : null}

      <div className="chat__composerTop">
        <button
          type="button"
          className="chat__iconButton"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          aria-label="Attach files"
        >
          📎
        </button>

        <button
          type="button"
          className={`chat__iconButton ${isListening ? 'chat__iconButton--active' : ''} ${isSpeaking ? 'chat__iconButton--speaking' : ''}`}
          onPointerDown={handleVoicePointerDown}
          onPointerUp={handleVoicePointerUp}
          onPointerLeave={handleVoicePointerUp}
          disabled={disabled || (voiceState !== 'idle' && voiceState !== 'listening')}
          aria-label={isListening ? 'Recording - release to stop' : 'Push to talk'}
        >
          {isListening ? '🎙️' : '🎤'}
        </button>
      </div>

      <div className="chat__composerRow">
        <textarea
          className="chat__textarea"
          placeholder="Message DASH…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={disabled}
          rows={1}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />

        <button className="chat__sendButton" type="button" onClick={handleSend} disabled={disabled || !trimmed}>
          Send
        </button>
      </div>

      <div className="chat__composerHint">
        Enter to send · Shift+Enter for newline
        {isSupported ? ' · Hold 🎤 or Space for push-to-talk' : null}
      </div>
    </div>
  );
}

