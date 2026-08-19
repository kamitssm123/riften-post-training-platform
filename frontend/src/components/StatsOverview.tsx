import { AlertTriangle, CheckCircle2, Layers, Scissors } from "lucide-react";
import type { Stats } from "../types/trace";
import { Card, CardContent } from "./ui/Card";
import { Progress } from "./ui/Progress";

interface Props {
  stats: Stats | null;
  resultCount: number;
}

function MetricTile({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <Card className="h-full">
      <CardContent className="!p-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-faint)]">
              {label}
            </div>
            <div
              className="mt-1 text-xl font-bold tabular-nums tracking-tight"
              style={accent ? { color: accent } : undefined}
            >
              {value}
            </div>
            {sub && <div className="mt-0.5 text-[10px] text-[var(--text-faint)]">{sub}</div>}
          </div>
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            style={{ background: "var(--bg-hover)", color: accent ?? "var(--text-dim)" }}
          >
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function StatsOverview({ stats, resultCount }: Props) {
  if (!stats) {
    return (
      <div className="shrink-0">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card h-[72px] animate-pulse" style={{ background: "var(--bg-hover)" }} />
          ))}
        </div>
      </div>
    );
  }

  const flaggedCount = stats.error_count + stats.truncated_count;
  const okRate = ((1 - stats.error_rate - stats.truncated_rate) * 100).toFixed(1);

  return (
    <div className="shrink-0 space-y-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricTile
          icon={<Layers size={15} />}
          label="Matching"
          value={resultCount}
          sub={`of ${stats.total} total`}
        />
        <MetricTile
          icon={<CheckCircle2 size={15} />}
          label="Healthy"
          value={`${okRate}%`}
          sub={`${flaggedCount} flagged (error or truncated)`}
          accent="var(--success)"
        />
        <MetricTile
          icon={<AlertTriangle size={15} />}
          label="Errors"
          value={stats.error_count}
          sub={`${(stats.error_rate * 100).toFixed(1)}% rate`}
          accent="var(--error)"
        />
        <MetricTile
          icon={<Scissors size={15} />}
          label="Truncated"
          value={stats.truncated_count}
          sub={`${(stats.truncated_rate * 100).toFixed(1)}% rate`}
          accent="var(--warning)"
        />
      </div>

      <Card>
        <CardContent className="!p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-faint)]">
              Corpus health
            </span>
            <span className="text-[10px] text-[var(--text-faint)]">
              {stats.error_count + stats.truncated_count} issues of {stats.total}
            </span>
          </div>
          <div className="space-y-2">
            <div>
              <div className="mb-1 flex justify-between text-[10px]">
                <span className="text-[var(--text-dim)]">Errors</span>
                <span className="tabular-nums text-[var(--error)]">
                  {(stats.error_rate * 100).toFixed(1)}%
                </span>
              </div>
              <Progress value={stats.error_rate * 100} color="var(--error)" />
            </div>
            <div>
              <div className="mb-1 flex justify-between text-[10px]">
                <span className="text-[var(--text-dim)]">Truncated</span>
                <span className="tabular-nums text-[var(--warning)]">
                  {(stats.truncated_rate * 100).toFixed(1)}%
                </span>
              </div>
              <Progress value={stats.truncated_rate * 100} color="var(--warning)" />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
