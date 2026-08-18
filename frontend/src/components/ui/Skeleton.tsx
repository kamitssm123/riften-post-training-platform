export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md ${className}`}
      style={{ background: "var(--bg-hover)" }}
    />
  );
}

export function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="p-4 space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 flex-1" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-32" />
        </div>
      ))}
    </div>
  );
}
