import type { ExportPreview } from "../types/exportPreview";
import { StatBadge } from "./StatBadge";
import { Tooltip } from "./ui/Tooltip";

interface Props {
  preview: ExportPreview | null;
  loading: boolean;
  onSelectTrace: (traceId: string) => void;
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

export function ExportPreviewBadges({ preview, loading, onSelectTrace }: Props) {
  if (loading || !preview) {
    return (
      <div className="mt-2 flex items-center gap-1.5">
        <span className="chip animate-pulse-soft">SFT: …</span>
        <span className="chip animate-pulse-soft">Preference: …</span>
      </div>
    );
  }

  const { sft, preference } = preview;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
      <Tooltip content={sft.detail ?? ""}>
        <span className="inline-flex">
          <StatBadge
            label={sft.included ? "SFT: included" : `SFT: excluded — ${sft.reason}`}
            tone={sft.included ? "success" : "error"}
          />
        </span>
      </Tooltip>

      {preference.eligible ? (
        <span className="inline-flex items-center gap-1">
          <Tooltip content={preference.detail ?? ""}>
            <span className="inline-flex">
              <StatBadge
                label={`Preference: eligible — ${preference.role} side (${preference.source})`}
                tone="info"
              />
            </span>
          </Tooltip>
          {preference.paired_with_trace_id && (
            <button
              onClick={() => onSelectTrace(preference.paired_with_trace_id!)}
              className="btn-ghost !px-1.5 !py-0.5 font-mono !text-[10px] underline decoration-dotted"
              title="Jump to paired trace"
            >
              paired with #{shortId(preference.paired_with_trace_id)}
            </button>
          )}
        </span>
      ) : (
        <Tooltip content={preference.detail ?? ""}>
          <span className="inline-flex">
            <StatBadge label="Preference: not eligible" tone="dim" />
          </span>
        </Tooltip>
      )}
    </div>
  );
}
