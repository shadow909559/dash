import { useEffect, useState } from "react";
import "./Notification.css";

export interface NotificationProps {
  id: number;
  title: string;
  message: string;
  type: "info" | "success" | "error";
  onDismiss: (id: number) => void;
}

export const Notification = ({
  id,
  title,
  message,
  type,
  onDismiss,
}: NotificationProps) => {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onDismiss(id), 500);
    }, 5000);

    return () => clearTimeout(timer);
  }, [id, onDismiss]);

  return (
    <div
      className={`notification notification--${type} ${
        exiting ? "notification--exit" : ""
      }`}
    >
      <div className="notification__icon"></div>
      <div className="notification__content">
        <div className="notification__title">{title}</div>
        <div className="notification__message">{message}</div>
      </div>
    </div>
  );
};