import { ALL_FEEDBACK, ALL_MODELS, type Stats, type TraceFilters } from "../types/trace";

interface Props {
  filters: TraceFilters;
  onChange: (next: TraceFilters) => void;
  stats: Stats | null;
  resultCount: number | null;
}

function toggleInArray(arr: string[], value: string): string[] {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
}

export function FilterRail({ filters, onChange, stats, resultCount }: Props) {
  return (
    <aside className="flex w-64 shrink-0 flex-col gap-6 border-r border-[var(--border)] px-4 py-5 text-[12px]">
      <div>
        <div className="text-[11px] uppercase tracking-wider text-[var(--text-faint)]">
          Result
        </div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">
          {resultCount ?? "—"}
        </div>
        {stats && (
          <div className="mt-1 text-[var(--text-dim)]">
            of {stats.total} traces &middot; {(stats.error_rate * 100).toFixed(1)}% error &middot;{" "}
            {(stats.truncated_rate * 100).toFixed(1)}% truncated
          </div>
        )}
      </div>

      <FilterSection title="Model">
        <div className="flex flex-col gap-1.5">
          {ALL_MODELS.map((m) => (
            <label key={m} className="flex cursor-pointer items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.model.includes(m)}
                  onChange={() => onChange({ ...filters, model: toggleInArray(filters.model, m) })}
                  className="accent-[var(--accent)]"
                />
                <span className="font-mono text-[11px]">{m}</span>
              </span>
              <span className="text-[var(--text-faint)] tabular-nums">
                {stats?.per_model[m] ?? 0}
              </span>
            </label>
          ))}
        </div>
      </FilterSection>

      <FilterSection title="Feedback">
        <div className="flex gap-1.5">
          {ALL_FEEDBACK.map((f) => (
            <button
              key={f}
              onClick={() => onChange({ ...filters, feedback: toggleInArray(filters.feedback, f) })}
              className={`rounded-sm border px-2 py-1 text-[11px] capitalize transition-colors ${
                filters.feedback.includes(f)
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-[var(--border)] text-[var(--text-dim)] hover:border-[var(--border-strong)]"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </FilterSection>

      <FilterSection title="Cost (USD)">
        <RangeInputs
          min={filters.min_cost}
          max={filters.max_cost}
          step={0.001}
          onChange={(min, max) => onChange({ ...filters, min_cost: min, max_cost: max })}
        />
      </FilterSection>

      <FilterSection title="Latency (ms)">
        <RangeInputs
          min={filters.min_latency}
          max={filters.max_latency}
          step={50}
          onChange={(min, max) => onChange({ ...filters, min_latency: min, max_latency: max })}
        />
      </FilterSection>

      <FilterSection title="Flags">
        <div className="flex flex-col gap-1.5">
          <ToggleRow
            label="Truncated only"
            value={filters.truncated}
            onChange={(v) => onChange({ ...filters, truncated: v })}
          />
          <ToggleRow
            label="Errored only"
            value={filters.errored}
            onChange={(v) => onChange({ ...filters, errored: v })}
          />
        </div>
      </FilterSection>

      {filters.session_id && (
        <FilterSection title="Session">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-mono text-[11px] text-[var(--text-dim)]">
              {filters.session_id}
            </span>
            <button
              onClick={() => onChange({ ...filters, session_id: null })}
              className="text-[var(--text-faint)] hover:text-[var(--text)]"
            >
              clear
            </button>
          </div>
        </FilterSection>
      )}

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
        className="mt-auto self-start text-[11px] text-[var(--text-faint)] hover:text-[var(--text)]"
      >
        Reset all filters
      </button>
    </aside>
  );
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-[11px] uppercase tracking-wider text-[var(--text-faint)]">
        {title}
      </div>
      {children}
    </div>
  );
}

function ToggleRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (v: boolean | null) => void;
}) {
  return (
    <button
      onClick={() => onChange(value === true ? null : true)}
      className={`flex items-center justify-between rounded-sm border px-2 py-1 text-left text-[11px] transition-colors ${
        value === true
          ? "border-[var(--accent)] text-[var(--accent)]"
          : "border-[var(--border)] text-[var(--text-dim)] hover:border-[var(--border-strong)]"
      }`}
    >
      {label}
    </button>
  );
}

function RangeInputs({
  min,
  max,
  step,
  onChange,
}: {
  min: number | null;
  max: number | null;
  step: number;
  onChange: (min: number | null, max: number | null) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        step={step}
        placeholder="min"
        value={min ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value), max)}
        className="w-full rounded-sm border border-[var(--border)] bg-transparent px-2 py-1 text-[11px] outline-none focus:border-[var(--border-strong)]"
      />
      <span className="text-[var(--text-faint)]">–</span>
      <input
        type="number"
        step={step}
        placeholder="max"
        value={max ?? ""}
        onChange={(e) => onChange(min, e.target.value === "" ? null : Number(e.target.value))}
        className="w-full rounded-sm border border-[var(--border)] bg-transparent px-2 py-1 text-[11px] outline-none focus:border-[var(--border-strong)]"
      />
    </div>
  );
}
