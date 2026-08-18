import { ChevronLeft, ChevronRight } from "lucide-react";
import { getPageSlots } from "../utils/pagination";

interface Props {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}

function PageSlotBox({
  slot,
  current,
  onChange,
}: {
  slot: ReturnType<typeof getPageSlots>[number];
  current: number;
  onChange: (page: number) => void;
}) {
  if (slot.kind === "empty") {
    return <div className="h-7 w-7 shrink-0" aria-hidden />;
  }

  if (slot.kind === "ellipsis") {
    return (
      <div
        className="flex h-7 w-7 shrink-0 items-center justify-center text-[var(--text-faint)]"
        aria-hidden
      >
        …
      </div>
    );
  }

  return (
    <button
      onClick={() => onChange(slot.page)}
      className={`btn !h-7 !w-7 shrink-0 !p-0 tabular-nums ${current === slot.page ? "btn-active" : ""}`}
      aria-current={current === slot.page ? "page" : undefined}
      aria-label={`Page ${slot.page}`}
    >
      {slot.page}
    </button>
  );
}

export function Pagination({ page, totalPages, onChange }: Props) {
  const slots = getPageSlots(page, totalPages);

  return (
    <div className="flex items-center gap-1.5">
      <button
        disabled={page <= 1}
        onClick={() => onChange(Math.max(1, page - 1))}
        className="btn !px-2.5"
      >
        <ChevronLeft size={14} />
        Prev
      </button>

      <div className="flex items-center gap-1.5">
        {slots.map((slot, i) => (
          <PageSlotBox key={i} slot={slot} current={page} onChange={onChange} />
        ))}
      </div>

      <button
        disabled={page >= totalPages}
        onClick={() => onChange(Math.min(totalPages, page + 1))}
        className="btn !px-2.5"
      >
        Next
        <ChevronRight size={14} />
      </button>
    </div>
  );
}
