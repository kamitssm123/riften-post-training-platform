import { AlertTriangle, Clock, DollarSign, Filter, RotateCcw, Scissors, X } from "lucide-react";
import { ALL_FEEDBACK, ALL_MODELS, type Stats, type TraceFilters } from "../types/trace";
import { Card, CardContent } from "./ui/Card";
import { CollapsibleSection } from "./ui/Collapsible";
import { Progress } from "./ui/Progress";
import { Switch } from "./ui/Switch";

interface Props {
  filters: TraceFilters;
  onChange: (next: TraceFilters) => void;
  stats: Stats | null;
  resultCount: number | null;
}

function toggleInArray(arr: string[], value: string): string[] {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
}

const FEEDBACK_COLORS: Record<string, string> = {
  weak: "var(--error)",
  ok: "var(--info)",
  strong: "var(--success)",
};

export function FilterRail({ filters, onChange, stats, resultCount }: Props) {
  const activeFilterCount = [
    filters.model.length > 0,
    filters.feedback.length > 0,
    filters.min_cost !== null || filters.max_cost !== null,
    filters.min_latency !== null || filters.max_latency !== null,
    filters.truncated !== null,
    filters.errored !== null,
    filters.session_id !== null,
  ].filter(Boolean).length;

  const maxModelCount = stats
    ? Math.max(...ALL_MODELS.map((m) => stats.per_model[m] ?? 0), 1)
    : 1;

  return (
    <aside
      className="flex w-72 shrink-0 flex-col border-r text-[12px] min-h-0"
      style={{
        borderColor: "var(--border)",
        background: "var(--bg-subtle)",
      }}
    >
      <div className="flex shrink-0 items-center gap-2 px-4 pb-2 pt-4">
        <Filter size={14} className="text-[var(--brand)]" />
        <span className="text-[12px] font-semibold">Filters</span>
        {activeFilterCount > 0 && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold"
            style={{ background: "var(--brand-dim)", color: "var(--brand)" }}
          >
            {activeFilterCount} active
          </span>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pb-4">
      <Card glow className="shrink-0">
        <CardContent className="!p-3.5">
          <div className="section-label">Result</div>
          <div className="mt-1.5 text-4xl font-bold tabular-nums tracking-tight">
            {resultCount ?? "—"}
          </div>
          {stats && (
            <div className="mt-3 space-y-2">
              <div className="text-[11px] text-[var(--text-dim)]">
                of {stats.total} traces in corpus
              </div>
              <div className="flex gap-2">
                <div
                  className="flex-1 rounded-lg px-2.5 py-2 text-center"
                  style={{ background: "var(--error-dim)" }}
                >
                  <div className="text-[10px] text-[var(--text-faint)]">Error</div>
                  <div className="text-sm font-bold tabular-nums text-[var(--error)]">
                    {(stats.error_rate * 100).toFixed(1)}%
                  </div>
                </div>
                <div
                  className="flex-1 rounded-lg px-2.5 py-2 text-center"
                  style={{ background: "var(--warning-dim)" }}
                >
                  <div className="text-[10px] text-[var(--text-faint)]">Truncated</div>
                  <div className="text-sm font-bold tabular-nums text-[var(--warning)]">
                    {(stats.truncated_rate * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <CollapsibleSection
        title="Model"
        badge={
          filters.model.length > 0 ? (
            <span className="chip">{filters.model.length}</span>
          ) : undefined
        }
      >
        <div className="flex flex-col gap-0.5">
          {ALL_MODELS.map((m) => {
            const checked = filters.model.includes(m);
            const count = stats?.per_model[m] ?? 0;
            return (
              <label
                key={m}
                className={`flex cursor-pointer flex-col gap-1.5 rounded-lg px-2.5 py-2 transition-all duration-150 ${
                  checked ? "bg-[var(--brand-dim)]" : "hover:bg-[var(--bg-hover)]"
                }`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2.5">
                    <span
                      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all ${
                        checked
                          ? "border-[var(--brand)] bg-[var(--brand)]"
                          : "border-[var(--border-strong)]"
                      }`}
                    >
                      {checked && (
                        <svg viewBox="0 0 10 8" className="h-2.5 w-3">
                          <path d="M1 4l2.5 2.5L9 1" stroke="white" strokeWidth="1.5" fill="none" />
                        </svg>
                      )}
                    </span>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() =>
                        onChange({ ...filters, model: toggleInArray(filters.model, m) })
                      }
                      className="sr-only"
                    />
                    <span className="font-mono text-[11px]">{m}</span>
                  </span>
                  <span className="chip tabular-nums">{count}</span>
                </span>
                {stats && (
                  <Progress value={count} max={maxModelCount} color="var(--brand)" />
                )}
              </label>
            );
          })}
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title="Feedback"
        badge={
          filters.feedback.length > 0 ? (
            <span className="chip">{filters.feedback.length}</span>
          ) : undefined
        }
      >
        <div className="flex gap-1.5">
          {ALL_FEEDBACK.map((f) => {
            const active = filters.feedback.includes(f);
            return (
              <button
                key={f}
                onClick={() =>
                  onChange({ ...filters, feedback: toggleInArray(filters.feedback, f) })
                }
                className={`flex-1 rounded-lg border px-2 py-2 text-[11px] font-medium capitalize transition-all duration-150 ${
                  active ? "btn-active" : "border-[var(--border)] text-[var(--text-dim)] hover:bg-[var(--bg-hover)]"
                }`}
                style={active ? { borderColor: FEEDBACK_COLORS[f] } : undefined}
              >
                {f}
              </button>
            );
          })}
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Cost (USD)">
        <RangeInputs
          icon={<DollarSign size={12} className="text-[var(--text-faint)]" />}
          min={filters.min_cost}
          max={filters.max_cost}
          step={0.001}
          onChange={(min, max) => onChange({ ...filters, min_cost: min, max_cost: max })}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Latency (ms)">
        <RangeInputs
          icon={<Clock size={12} className="text-[var(--text-faint)]" />}
          min={filters.min_latency}
          max={filters.max_latency}
          step={50}
          onChange={(min, max) => onChange({ ...filters, min_latency: min, max_latency: max })}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Flags">
        <div className="flex flex-col gap-2">
          <FlagSwitch
            icon={<Scissors size={13} />}
            label="Truncated only"
            checked={filters.truncated === true}
            onCheckedChange={(v) => onChange({ ...filters, truncated: v ? true : null })}
          />
          <FlagSwitch
            icon={<AlertTriangle size={13} />}
            label="Errored only"
            checked={filters.errored === true}
            onCheckedChange={(v) => onChange({ ...filters, errored: v ? true : null })}
          />
        </div>
      </CollapsibleSection>

      {filters.session_id && (
        <CollapsibleSection title="Session" defaultOpen>
          <Card>
            <CardContent className="!flex !items-center !justify-between !gap-2 !p-2.5">
              <span className="truncate font-mono text-[11px] text-[var(--text-dim)]">
                {filters.session_id}
              </span>
              <button
                onClick={() => onChange({ ...filters, session_id: null })}
                className="btn-ghost !p-1"
                aria-label="Clear session filter"
              >
                <X size={12} />
              </button>
            </CardContent>
          </Card>
        </CollapsibleSection>
      )}

      </div>

      <div
        className="shrink-0 border-t px-4 py-3"
        style={{ borderColor: "var(--border)" }}
      >
      <button
        onClick={() =>
          onChange({
            model: [],
            min_cost: null,
            max_cost: null,
            min_latency: null,
            max_latency: null,
            feedback: [],
            truncated: null,
            errored: null,
            session_id: null,
          })
        }
        className="btn flex w-full items-center justify-center gap-1.5"
        disabled={activeFilterCount === 0}
      >
        <RotateCcw size={12} />
        Reset all filters
      </button>
      </div>
    </aside>
  );
}

function FlagSwitch({
  icon,
  label,
  checked,
  onCheckedChange,
}: {
  icon: React.ReactNode;
  label: string;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
}) {
  return (
    <div
      className={`flex items-center justify-between rounded-lg border px-3 py-2.5 transition-colors ${
        checked ? "border-[var(--accent)] bg-[var(--accent-dim)]" : "border-[var(--border)]"
      }`}
    >
      <span className="flex items-center gap-2 text-[11px] text-[var(--text-dim)]">
        {icon}
        {label}
      </span>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}

function RangeInputs({
  icon,
  min,
  max,
  step,
  onChange,
}: {
  icon?: React.ReactNode;
  min: number | null;
  max: number | null;
  step: number;
  onChange: (min: number | null, max: number | null) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <input
        type="number"
        step={step}
        placeholder="min"
        value={min ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value), max)}
        className="input-field"
      />
      <span className="text-[var(--text-faint)]">–</span>
      <input
        type="number"
        step={step}
        placeholder="max"
        value={max ?? ""}
        onChange={(e) => onChange(min, e.target.value === "" ? null : Number(e.target.value))}
        className="input-field"
      />
    </div>
  );
}
