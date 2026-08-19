export interface SftPreview {
  included: boolean;
  reason: string | null;
  detail: string | null;
}

export interface PreferencePreview {
  eligible: boolean;
  role: "chosen" | "rejected" | null;
  source: string | null;
  paired_with_trace_id: string | null;
  detail: string | null;
}

export interface ExportPreview {
  sft: SftPreview;
  preference: PreferencePreview;
}
