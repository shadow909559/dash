import { useEffect, useState, useRef } from "react";
import { Activity, Zap, Cpu, MessageSquare, Search, Code, Settings } from "lucide-react";
import { useActivityStore } from "@/stores/activityStore";

interface ActivityItem {
  id: string;
  message: string;
  type: "system" | "ai" | "user" | "error" | "tool";
  timestamp: Date;
}

const typeIcons = {
  system: <Activity size={14} />,
  ai: <Zap size={14} />,
  user: <MessageSquare size={14} />,
  error: <Settings size={14} />,
  tool: <Cpu size={14} />,
};

const typeColors = {
  system: "rgba(0, 255, 255, 0.9)",
  ai: "rgba(168, 85, 247, 0.9)",
  user: "rgba(74, 222, 128, 0.9)",
  error: "rgba(239, 68, 68, 0.9)",
  tool: "rgba(251, 191, 36, 0.9)",
};

export default function ActivityPanel() {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const { items: storeActivities } = useActivityStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Convert store activities to local format with safe date handling
    const formattedActivities = storeActivities.map((activity: any, index: number) => {
      // Safe timestamp conversion
      let timestamp: Date;
      try {
        const timeValue = activity.time;
        if (typeof timeValue === 'number') {
          // Handle both seconds and milliseconds
          timestamp = new Date(timeValue < 10000000000 ? timeValue * 1000 : timeValue);
        } else if (typeof timeValue === 'string') {
          timestamp = new Date(timeValue);
        } else {
          timestamp = new Date();
        }
        
        // Check if the date is valid
        if (isNaN(timestamp.getTime())) {
          timestamp = new Date();
        }
      } catch {
        timestamp = new Date();
      }
      
      return {
        id: `activity_${index}`,
        message: activity.message,
        type: activity.kind as "system" | "ai" | "user" | "error" | "tool",
        timestamp,
      };
    });
    setActivities(formattedActivities);
  }, [storeActivities]);

  useEffect(() => {
    // Auto-scroll to bottom when new activities arrive
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activities]);

  const formatTime = (date: Date) => {
    // Safe date formatter that handles invalid dates
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      return "Just now";
    }
    
    try {
      return date.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch {
      return "Just now";
    }
  };

  return (
    <div
      style={{
        height: "100%",
        backgroundColor: "rgba(0, 10, 30, 0.85)",
        border: "1px solid rgba(0, 255, 255, 0.3)",
        borderRadius: 16,
        backdropFilter: "blur(30px)",
        WebkitBackdropFilter: "blur(30px)",
        display: "flex",
        flexDirection: "column",
        boxShadow: "0 0 30px rgba(0, 255, 255, 0.2), 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(0, 255, 255, 0.1)",
        overflow: "auto",
      }}
    >
      <div
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid rgba(0, 255, 255, 0.2)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "rgba(0, 255, 255, 0.95)",
            letterSpacing: "0.5px",
            textTransform: "uppercase",
            textShadow: "0 0 8px rgba(0, 255, 255, 0.5)",
          }}
        >
          Activity Feed
        </span>
        <Activity size={16} color="rgba(0, 255, 255, 0.7)" />
      </div>

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        {activities.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              color: "rgba(255, 255, 255, 0.4)",
              fontSize: 12,
              padding: 20,
            }}
          >
            No recent activity
          </div>
        ) : (
          activities.map((activity) => (
            <div
              key={activity.id}
              style={{
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
                padding: 10,
                borderRadius: 8,
                backgroundColor: "rgba(0, 20, 40, 0.5)",
                border: "1px solid rgba(0, 255, 255, 0.1)",
                transition: "all 0.2s ease",
              }}
            >
              <div
                style={{
                  color: typeColors[activity.type],
                  marginTop: 2,
                  flexShrink: 0,
                }}
              >
                {typeIcons[activity.type]}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 12,
                    color: "rgba(255, 255, 255, 0.9)",
                    lineHeight: 1.4,
                    wordBreak: "break-word",
                  }}
                >
                  {activity.message}
                </div>
                <div
                  style={{
                    fontSize: 10,
                    color: "rgba(255, 255, 255, 0.5)",
                    marginTop: 4,
                  }}
                >
                  {formatTime(activity.timestamp)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
