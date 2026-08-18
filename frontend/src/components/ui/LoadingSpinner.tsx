import { Loader2 } from "lucide-react";

export function LoadingSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-[12px] text-[var(--text-faint)]">
      <Loader2 size={20} className="animate-spin-slow text-[var(--accent)]" />
      <span>{label}</span>
    </div>
  );
}
