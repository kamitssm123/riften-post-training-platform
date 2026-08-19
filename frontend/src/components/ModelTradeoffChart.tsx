import type { ModelTradeoff } from "../types/modelTradeoff";
import { colorForModel } from "../utils/modelColors";
import { Tooltip } from "./ui/Tooltip";

interface Props {
  items: ModelTradeoff[];
}

const WIDTH = 640;
const HEIGHT = 320;
const MARGIN = { top: 16, right: 24, bottom: 40, left: 48 };
const PLOT_W = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_H = HEIGHT - MARGIN.top - MARGIN.bottom;

function radiusFor(traceCount: number, maxCount: number): number {
  const t = maxCount > 0 ? Math.sqrt(traceCount / maxCount) : 0;
  return 7 + t * 16;
}

export function ModelTradeoffChart({ items }: Props) {
  const plottable = items.filter((i) => i.avg_quality_score !== null && i.avg_cost_usd !== null);
  const unplottable = items.filter((i) => !(i.avg_quality_score !== null && i.avg_cost_usd !== null));

  if (plottable.length === 0) {
    return (
      <div
        className="flex h-[240px] items-center justify-center rounded-xl border border-dashed text-[12px] text-[var(--text-faint)]"
        style={{ borderColor: "var(--border)" }}
      >
        No model has feedback coverage yet -- nothing to plot.
      </div>
    );
  }

  const costs = plottable.map((i) => i.avg_cost_usd as number).filter((c) => c > 0);
  const minCost = Math.min(...costs);
  const maxCost = Math.max(...costs);
  // Costs span two orders of magnitude across models -- a log scale keeps
  // the cheap, high-volume models from collapsing into a single pixel.
  const logMin = Math.log10(minCost) - 0.3;
  const logMax = Math.log10(maxCost) + 0.3;
  const maxCount = Math.max(...plottable.map((i) => i.trace_count));

  const xFor = (cost: number) => {
    const t = (Math.log10(cost) - logMin) / (logMax - logMin || 1);
    return MARGIN.left + t * PLOT_W;
  };
  const yFor = (quality: number) => MARGIN.top + (1 - quality) * PLOT_H;

  const xTicks = [minCost, Math.sqrt(minCost * maxCost), maxCost];
  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" style={{ maxHeight: 340 }}>
        {/* gridlines */}
        {yTicks.map((yt) => (
          <line
            key={`gy-${yt}`}
            x1={MARGIN.left}
            x2={WIDTH - MARGIN.right}
            y1={yFor(yt)}
            y2={yFor(yt)}
            stroke="var(--border)"
            strokeWidth={1}
          />
        ))}

        {/* axes */}
        <line
          x1={MARGIN.left}
          x2={MARGIN.left}
          y1={MARGIN.top}
          y2={HEIGHT - MARGIN.bottom}
          stroke="var(--border-strong)"
          strokeWidth={1}
        />
        <line
          x1={MARGIN.left}
          x2={WIDTH - MARGIN.right}
          y1={HEIGHT - MARGIN.bottom}
          y2={HEIGHT - MARGIN.bottom}
          stroke="var(--border-strong)"
          strokeWidth={1}
        />

        {/* y ticks */}
        {yTicks.map((yt) => (
          <text
            key={`yl-${yt}`}
            x={MARGIN.left - 8}
            y={yFor(yt)}
            textAnchor="end"
            dominantBaseline="middle"
            fontSize={10}
            fill="var(--text-faint)"
          >
            {yt.toFixed(2)}
          </text>
        ))}

        {/* x ticks */}
        {xTicks.map((xt, i) => (
          <text
            key={`xl-${i}`}
            x={xFor(xt)}
            y={HEIGHT - MARGIN.bottom + 16}
            textAnchor="middle"
            fontSize={10}
            fill="var(--text-faint)"
          >
            ${xt < 0.001 ? xt.toExponential(1) : xt.toFixed(4)}
          </text>
        ))}

        <text
          x={MARGIN.left + PLOT_W / 2}
          y={HEIGHT - 4}
          textAnchor="middle"
          fontSize={10}
          fill="var(--text-faint)"
          fontWeight={600}
        >
          Avg cost per call (log scale)
        </text>
        <text
          x={-(MARGIN.top + PLOT_H / 2)}
          y={12}
          textAnchor="middle"
          fontSize={10}
          fill="var(--text-faint)"
          fontWeight={600}
          transform="rotate(-90)"
        >
          Avg quality score
        </text>

        {plottable.map((item) => {
          const cx = xFor(item.avg_cost_usd as number);
          const cy = yFor(item.avg_quality_score as number);
          const r = radiusFor(item.trace_count, maxCount);
          const color = colorForModel(item.model);
          return (
            <Tooltip
              key={item.model}
              content={
                <div className="space-y-0.5">
                  <div className="font-semibold text-[var(--text)]">{item.model}</div>
                  <div>quality {item.avg_quality_score?.toFixed(2)} (coverage {(item.feedback_coverage * 100).toFixed(0)}%)</div>
                  <div>cost ${item.avg_cost_usd?.toFixed(6)} / call</div>
                  <div>{item.trace_count} traces</div>
                </div>
              }
            >
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill={color}
                fillOpacity={0.28}
                stroke={color}
                strokeWidth={2}
                className="cursor-pointer transition-opacity duration-150 hover:fill-opacity-50"
              />
            </Tooltip>
          );
        })}
      </svg>

      {/* legend */}
      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1.5 px-1">
        {plottable.map((item) => (
          <div key={item.model} className="flex items-center gap-1.5 text-[10px] text-[var(--text-dim)]">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: colorForModel(item.model) }}
            />
            {item.model}
          </div>
        ))}
        <span className="text-[10px] text-[var(--text-faint)]">· point size = trace volume</span>
      </div>

      {unplottable.length > 0 && (
        <div
          className="mt-3 rounded-lg border px-3 py-2 text-[11px] text-[var(--text-faint)]"
          style={{ borderColor: "var(--border)", background: "var(--bg-subtle)" }}
        >
          Not plotted (no feedback coverage yet): {unplottable.map((i) => i.model).join(", ")}
        </div>
      )}
    </div>
  );
}
