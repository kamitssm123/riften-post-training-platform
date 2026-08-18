import { PanelCloseButton } from "./PanelCloseButton";

export function PanelHeader({
  title,
  subtitle,
  icon,
  onClose,
  children,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  onClose: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div
      className="border-b px-4 py-3.5"
      style={{
        borderColor: "var(--border)",
        background: "linear-gradient(180deg, var(--bg-subtle) 0%, var(--panel-bg) 100%)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {icon && (
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
                style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
              >
                {icon}
              </div>
            )}
            <div className="min-w-0">
              <div className="truncate text-[13px] font-semibold">{title}</div>
              {subtitle && (
                <div className="mt-0.5 text-[11px] text-[var(--text-faint)]">{subtitle}</div>
              )}
            </div>
          </div>
          {children}
        </div>
        <PanelCloseButton onClick={onClose} />
      </div>
    </div>
  );
}
