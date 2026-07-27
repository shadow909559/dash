import { useEffect, useState, useMemo, useCallback, memo } from "react";
import { SystemMonitorService, type SystemSnapshot } from "@/lib/systemMonitor";

// Memoized widget item to prevent unnecessary re-renders of the entire list
const WidgetItem = memo(function WidgetItem({
  label,
  valueText,
  color,
  title,
}: {
  label: string;
  valueText: string;
  color: string;
  title: string;
}) {
  const wstyle: React.CSSProperties = useMemo(
    () => ({
      padding: "10px 14px",
      borderRadius: 12,
      display: "flex",
      alignItems: "center",
      gap: 10,
      fontSize: 12,
    }),
    []
  );
  return (
    <div className="glass" style={wstyle} title={title}>
      <div
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: color,
        }}
      />
      <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{label}</span>
      <span style={{ color: "var(--text-secondary)" }}>{valueText}</span>
    </div>
  );
});

export default function DesktopWidgets() {
  const [sys, setSys] = useState<SystemSnapshot | null>(null);
  const [connected, setConnected] = useState(false);

  // Derived values computed via useMemo to prevent recalculations
  const cpuPercent = useMemo(() => sys?.cpu?.percentage ?? null, [sys?.cpu?.percentage]);
  const ramPercent = useMemo(() => sys?.ram?.percent ?? null, [sys?.ram?.percent]);
  const storageUsedGb = useMemo(() => sys?.storage?.used_gb ?? null, [sys?.storage?.used_gb]);
  const storageTotalGb = useMemo(() => sys?.storage?.total_gb ?? null, [sys?.storage?.total_gb]);

  const cpuValue = useMemo(
    () => (cpuPercent != null ? `${Math.round(cpuPercent)}%` : "---"),
    [cpuPercent]
  );
  const ramValue = useMemo(
    () => (ramPercent != null ? `${Math.round(ramPercent)}%` : "---"),
    [ramPercent]
  );
  const diskPercent = useMemo(
    () =>
      storageTotalGb != null && storageUsedGb != null
        ? (storageUsedGb / storageTotalGb) * 100
        : null,
    [storageTotalGb, storageUsedGb]
  );
  const diskValue = useMemo(
    () => (diskPercent != null ? `${Math.round(diskPercent)}%` : "---"),
    [diskPercent]
  );

  const cpuColor = useMemo(
    () =>
      cpuPercent == null
        ? "var(--success)"
        : cpuPercent > 80
        ? "var(--danger)"
        : cpuPercent > 50
        ? "var(--warning)"
        : "var(--success)",
    [cpuPercent]
  );
  const ramColor = useMemo(
    () =>
      ramPercent == null
        ? "var(--success)"
        : ramPercent > 80
        ? "var(--danger)"
        : ramPercent > 50
        ? "var(--warning)"
        : "var(--success)",
    [ramPercent]
  );
  const diskColor = useMemo(
    () =>
      diskPercent == null
        ? "var(--success)"
        : diskPercent > 85
        ? "var(--danger)"
        : diskPercent > 60
        ? "var(--warning)"
        : "var(--success)",
    [diskPercent]
  );

  // Memoized disk percent calculation
  const calcDiskPercent = useCallback((): number | null => {
    if (!sys?.storage?.total_gb || !sys?.storage?.used_gb) return null;
    return (sys.storage.used_gb / sys.storage.total_gb) * 100;
  }, [sys?.storage?.total_gb, sys?.storage?.used_gb]);

  // Monitor connection - single effect, no unnecessary state changes
  useEffect(() => {
    const monitor = new SystemMonitorService(
      (data: SystemSnapshot) => {
        setSys((prev) => {
          // Only update if data actually changed (shallow compare snapshot keys)
          if (prev && JSON.stringify(prev) === JSON.stringify(data)) return prev;
          return data;
        });
        setConnected(true);
      },
      (conn: boolean) => setConnected(conn)
    );
    return () => {
      monitor.disconnect();
    };
  }, []);

  // Hide when not connected
  if (!connected || !sys) return null;

  return (
    <div style={{ position: "fixed", bottom: 100, right: 24, zIndex: 998 }}>
      <WidgetItem
        label="CPU"
        valueText={cpuValue}
        color={cpuColor}
        title={`CPU: ${cpuPercent ?? "?"}%`}
      />
      <WidgetItem
        label="RAM"
        valueText={ramValue}
        color={ramColor}
        title={`RAM: ${storageUsedGb ?? "?"}GB / ${storageTotalGb ?? "?"}GB`}
      />
      <WidgetItem
        label="DISK"
        valueText={diskValue}
        color={diskColor}
        title={`Disk: ${storageUsedGb ?? "?"}GB / ${storageTotalGb ?? "?"}GB`}
      />
    </div>
  );
}
