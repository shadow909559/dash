import Skeleton from "@/components/Skeleton";

export default function DashboardLoading() {
  return (
    <div>
      <div className="page-header">
        <div>
          <Skeleton width={200} height={36} />
          <Skeleton width={300} height={20} style={{ marginTop: 8 }} />
        </div>
      </div>

      <div className="grid-4" style={{ marginBottom: 24 }}>
        <div className="glass-card" style={{ padding: 20 }}>
          <Skeleton circle width={24} height={24} style={{ marginBottom: 12 }} />
          <Skeleton width={80} height={32} style={{ marginBottom: 4 }} />
          <Skeleton width={120} height={16} />
        </div>
        <div className="glass-card" style={{ padding: 20 }}>
          <Skeleton circle width={24} height={24} style={{ marginBottom: 12 }} />
          <Skeleton width={80} height={32} style={{ marginBottom: 4 }} />
          <Skeleton width={120} height={16} />
        </div>
        <div className="glass-card" style={{ padding: 20 }}>
          <Skeleton circle width={24} height={24} style={{ marginBottom: 12 }} />
          <Skeleton width={80} height={32} style={{ marginBottom: 4 }} />
          <Skeleton width={120} height={16} />
        </div>
        <div className="glass-card" style={{ padding: 20 }}>
          <Skeleton circle width={24} height={24} style={{ marginBottom: 12 }} />
          <Skeleton width={80} height={32} style={{ marginBottom: 4 }} />
          <Skeleton width={120} height={16} />
        </div>
      </div>

      <div className="grid-2">
        <div className="glass-card" style={{ padding: 24 }}>
          <Skeleton width={150} height={24} style={{ marginBottom: 16 }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <Skeleton height={40} />
            <Skeleton height={40} />
            <Skeleton height={40} />
            <Skeleton height={40} />
          </div>
        </div>
        <div className="glass-card" style={{ padding: 24 }}>
          <Skeleton width={150} height={24} style={{ marginBottom: 16 }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Skeleton height={20} />
            <Skeleton height={20} />
            <Skeleton height={20} />
            <Skeleton height={20} />
          </div>
        </div>
      </div>
    </div>
  );
}