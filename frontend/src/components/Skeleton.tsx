export function Skeleton({ height = 24, width = "100%" }: { height?: number; width?: string | number }) {
  return (
    <div
      aria-hidden
      style={{
        height,
        width,
        borderRadius: 8,
        background: "linear-gradient(90deg, #eee 25%, #f5f5f5 50%, #eee 75%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.2s ease-in-out infinite",
      }}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="card">
      <Skeleton height={14} width="40%" />
      <div style={{ height: 12 }} />
      <Skeleton height={28} width="60%" />
    </div>
  );
}
