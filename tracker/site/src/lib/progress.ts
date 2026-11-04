import type { RowTuple, Status } from './types';

/** How much of a row counts as done. Rows are weighted equally (no hour estimates). */
export const WEIGHT: Record<Status, number> = {
  unknown: 0,
  not_implemented: 0,
  partial: 0.5,
  implemented: 0.85,
  fully_functional: 1,
  not_planned: 0,
};

export interface Tally {
  /** Rows per status. */
  counts: Record<Status, number>;
  /** Rows that count towards the total (everything but "not planned"). */
  total: number;
  /** Weighted done rows. */
  done: number;
  /** Percentage 0..100. */
  percent: number;
}

export function emptyCounts(): Record<Status, number> {
  return { unknown: 0, not_implemented: 0, partial: 0, implemented: 0, fully_functional: 0, not_planned: 0 };
}

export function tally(rows: Iterable<RowTuple>): Tally {
  const counts = emptyCounts();
  for (const r of rows) counts[r[3]]++;
  const total = Object.values(counts).reduce((a, b) => a + b, 0) - counts.not_planned;
  let done = 0;
  for (const s of Object.keys(counts) as Status[]) done += counts[s] * WEIGHT[s];
  return { counts, total, done, percent: total ? (done / total) * 100 : 0 };
}

/** "12.4%", "0%", "<0.1%". */
export function pct(p: number): string {
  if (p <= 0) return '0%';
  if (p < 0.1) return '<0.1%';
  return `${p < 10 ? p.toFixed(1) : Math.round(p)}%`;
}
