import { Monitor, Moon, Sun } from "lucide-react";
import type { Theme } from "../hooks/useTheme";

interface Props {
  theme: Theme;
  onChange: (theme: Theme) => void;
}

const OPTIONS: { value: Theme; icon: typeof Sun; label: string }[] = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "dark", icon: Moon, label: "Dark" },
  { value: "system", icon: Monitor, label: "System" },
];

export function ThemeSwitcher({ theme, onChange }: Props) {
  return (
    <div
      className="flex items-center rounded-xl border p-1"
      style={{ borderColor: "var(--border)", background: "var(--bg-raised)" }}
      role="group"
      aria-label="Theme"
    >
      {OPTIONS.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          onClick={() => onChange(value)}
          title={label}
          aria-label={label}
          aria-pressed={theme === value}
          className={`flex items-center justify-center rounded-lg p-2 transition-all duration-200 ${
            theme === value
              ? "shadow-sm"
              : "text-[var(--text-faint)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
          }`}
          style={
            theme === value
              ? { background: "var(--brand-dim)", color: "var(--brand)" }
              : undefined
          }
        >
          <Icon size={14} strokeWidth={2} />
        </button>
      ))}
    </div>
  );
}
