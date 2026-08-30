import { createContext, useContext, useState, useCallback } from "react";
import { Notification, NotificationProps } from "./Notification";

interface NotificationContextType {
  addNotification: (notification: Omit<NotificationProps, "id" | "onDismiss">) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined
);

export const useNotifier = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error("useNotifier must be used within a NotificationProvider");
  }
  return context;
};

export const NotificationProvider = ({ children }: { children: React.ReactNode }) => {
  const [notifications, setNotifications] = useState<NotificationProps[]>([]);

  const addNotification = useCallback(
    (notification: Omit<NotificationProps, "id" | "onDismiss">) => {
      const id = Date.now();
      setNotifications((prev) => [
        ...prev,
        { ...notification, id, onDismiss: dismissNotification },
      ]);
    },
    []
  );

  const dismissNotification = useCallback((id: number) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <NotificationContext.Provider value={{ addNotification }}>
      {children}
      <div className="notification-container">
        {notifications.map((notification) => (
          <Notification key={notification.id} {...notification} />
        ))}
      </div>
    </NotificationContext.Provider>
  );
};