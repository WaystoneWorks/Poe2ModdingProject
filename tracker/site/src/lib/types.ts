/** The data `cargo xtask tracker build` writes to data.js (window.TRACKER_DATA). */
export type Status =
  | 'unknown'
  | 'not_implemented'
  | 'partial'
  | 'implemented'
  | 'fully_functional'
  | 'not_planned';

/** id, group, name, status, note, link, automatic. */
export type RowTuple = [string, string, string, Status, string, string, boolean];

export interface SectionData {
  id: string;
  title: string;
  description: string;
  rows: RowTuple[];
}

export interface Change {
  id: string;
  name: string;
  old: Status;
  new: Status;
  date: string;
  commit: string;
}

export interface TrackerData {
  edit: boolean;
  commit: string;
  repo: string | null;
  statuses: Status[];
  sections: SectionData[];
  recent: Change[];
}

export const LABELS: Record<Status, string> = {
  unknown: 'Unknown',
  not_implemented: 'Not implemented',
  partial: 'Partial',
  implemented: 'Implemented',
  fully_functional: 'Fully functional',
  not_planned: 'Not planned',
};
