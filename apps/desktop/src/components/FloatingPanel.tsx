import { useState, useRef, useEffect, ReactNode } from "react";
import { X, Minus, Maximize2 } from "lucide-react";

interface FloatingPanelProps {
  title: string;
  children: ReactNode;
  isOpen: boolean;
  onClose: () => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
  initialPosition?: { x: number; y: number };
  initialSize?: { width: number; height: number };
  minimizable?: boolean;
  maximizable?: boolean;
  resizable?: boolean;
  zIndex?: number;
}

export default function FloatingPanel({
  title,
  children,
  isOpen,
  onClose,
  onMinimize,
  onMaximize,
  initialPosition = { x: 100, y: 100 },
  initialSize = { width: 400, height: 300 },
  minimizable = true,
  maximizable = true,
  resizable = true,
  zIndex = 100,
}: FloatingPanelProps) {
  const [position, setPosition] = useState(initialPosition);
  const [size, setSize] = useState(initialSize);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const dragOffset = useRef({ x: 0, y: 0 });
  const resizeStart = useRef({ x: 0, y: 0, width: 0, height: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging && panelRef.current) {
        setPosition({
          x: e.clientX - dragOffset.current.x,
          y: e.clientY - dragOffset.current.y,
        });
      }
      if (isResizing && panelRef.current) {
        const newWidth = resizeStart.current.width + (e.clientX - resizeStart.current.x);
        const newHeight = resizeStart.current.height + (e.clientY - resizeStart.current.y);
        setSize({
          width: Math.max(300, newWidth),
          height: Math.max(200, newHeight),
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      setIsResizing(false);
    };

    if (isDragging || isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, isResizing]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (panelRef.current) {
      setIsDragging(true);
      dragOffset.current = {
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      };
    }
  };

  const handleResizeStart = (e: React.MouseEvent) => {
    if (panelRef.current) {
      setIsResizing(true);
      resizeStart.current = {
        x: e.clientX,
        y: e.clientY,
        width: size.width,
        height: size.height,
      };
    }
  };

  const handleMaximize = () => {
    if (isMaximized) {
      setSize(initialSize);
      setPosition(initialPosition);
      setIsMaximized(false);
    } else {
      setSize({ width: window.innerWidth - 40, height: window.innerHeight - 40 });
      setPosition({ x: 20, y: 20 });
      setIsMaximized(true);
    }
    onMaximize?.();
  };

  const handleMinimize = () => {
    setIsMinimized(!isMinimized);
    onMinimize?.();
  };

  if (!isOpen) return null;

  return (
    <div
      ref={panelRef}
      style={{
        position: "fixed",
        left: isMaximized ? 20 : position.x,
        top: isMaximized ? 20 : position.y,
        width: isMaximized ? "calc(100vw - 40px)" : size.width,
        height: isMinimized ? 40 : (isMaximized ? "calc(100vh - 40px)" : size.height),
        backgroundColor: "rgba(0, 10, 30, 0.95)",
        border: "1px solid rgba(0, 255, 255, 0.4)",
        borderRadius: 12,
        backdropFilter: "blur(30px)",
        WebkitBackdropFilter: "blur(30px)",
        zIndex,
        display: "flex",
        flexDirection: "column",
        boxShadow: "0 0 40px rgba(0, 255, 255, 0.3), 0 8px 32px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(0, 255, 255, 0.1)",
        overflow: "hidden",
        transition: isDragging || isResizing ? "none" : "all 0.2s ease",
      }}
    >
      {/* Header */}
      <div
        onMouseDown={handleMouseDown}
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid rgba(0, 255, 255, 0.2)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "move",
          backgroundColor: "rgba(0, 20, 40, 0.6)",
          userSelect: "none",
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "rgba(0, 255, 255, 0.95)",
            letterSpacing: "0.5px",
            textTransform: "uppercase",
            textShadow: "0 0 8px rgba(0, 255, 255, 0.5)",
          }}
        >
          {title}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          {minimizable && (
            <button
              onClick={handleMinimize}
              style={{
                background: "none",
                border: "none",
                color: "rgba(0, 255, 255, 0.7)",
                cursor: "pointer",
                padding: 4,
                borderRadius: 4,
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(0, 255, 255, 0.1)";
                e.currentTarget.style.color = "rgba(0, 255, 255, 1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "none";
                e.currentTarget.style.color = "rgba(0, 255, 255, 0.7)";
              }}
            >
              <Minus size={16} />
            </button>
          )}
          {maximizable && (
            <button
              onClick={handleMaximize}
              style={{
                background: "none",
                border: "none",
                color: "rgba(0, 255, 255, 0.7)",
                cursor: "pointer",
                padding: 4,
                borderRadius: 4,
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(0, 255, 255, 0.1)";
                e.currentTarget.style.color = "rgba(0, 255, 255, 1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "none";
                e.currentTarget.style.color = "rgba(0, 255, 255, 0.7)";
              }}
            >
              <Maximize2 size={16} />
            </button>
          )}
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "rgba(255, 100, 100, 0.7)",
              cursor: "pointer",
              padding: 4,
              borderRadius: 4,
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255, 100, 100, 0.1)";
              e.currentTarget.style.color = "rgba(255, 100, 100, 1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "none";
              e.currentTarget.style.color = "rgba(255, 100, 100, 0.7)";
            }}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Content */}
      {!isMinimized && (
        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: 16,
          }}
        >
          {children}
        </div>
      )}

      {/* Resize Handle */}
      {resizable && !isMaximized && !isMinimized && (
        <div
          onMouseDown={handleResizeStart}
          style={{
            position: "absolute",
            bottom: 0,
            right: 0,
            width: 20,
            height: 20,
            cursor: "se-resize",
            background: "linear-gradient(135deg, transparent 50%, rgba(0, 255, 255, 0.3) 50%)",
          }}
        />
      )}
    </div>
  );
}
