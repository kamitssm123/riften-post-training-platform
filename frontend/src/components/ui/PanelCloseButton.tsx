import { X } from "lucide-react";

export function PanelCloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="Close panel"
      className="btn-ghost !rounded-full !p-1.5 hover:!bg-[var(--bg-hover)]"
    >
      <X size={14} strokeWidth={2} />
    </button>
  );
}
