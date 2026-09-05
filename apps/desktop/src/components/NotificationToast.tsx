import React from "react";

export interface NotificationToastProps {
  isOpen?: boolean;
  onClose?: () => void;
}

const NotificationToast: React.FC<NotificationToastProps> = ({ isOpen, onClose }) => {
  if (isOpen === false) return null;
  if (!isOpen && !onClose) return null;
  return (
    <div style={{ position: "fixed", top: 20, right: 20, zIndex: 9999 }}>
      {onClose && (
        <button onClick={onClose} style={{ padding: "8px 16px", cursor: "pointer" }}>
          Close
        </button>
      )}
    </div>
  );
};

export default NotificationToast;
