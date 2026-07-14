export function TypingIndicator() {
  return (
    <div className="chat__typing" aria-live="polite">
      <span className="chat__typingDots">
        <span />
        <span />
        <span />
      </span>
      <span className="chat__typingText">Assistant is typing…</span>
    </div>
  );
}


