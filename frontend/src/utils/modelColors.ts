import { ALL_MODELS } from "../types/trace";

// Fixed model -> color assignment, reusing the app's existing status/accent
// tokens rather than introducing a new palette. Order is fixed (matches
// ALL_MODELS) and never reassigned based on which models are present in a
// given result set, so a model's color stays stable across views.
const PALETTE = [
  "var(--accent)",
  "var(--info)",
  "var(--brand)",
  "var(--success)",
  "var(--warning)",
];

const MODEL_COLOR: Record<string, string> = Object.fromEntries(
  ALL_MODELS.map((m, i) => [m, PALETTE[i % PALETTE.length]])
);

export function colorForModel(model: string): string {
  return MODEL_COLOR[model] ?? "var(--text-faint)";
}
