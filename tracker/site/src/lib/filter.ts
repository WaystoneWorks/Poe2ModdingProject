import type { RowTuple, SectionData, Status } from './types';

export interface Query {
  /** Free-text terms; every one must occur in the name, id, group, note or status. */
  terms: string[];
  is: Status[];
  notIs: Status[];
  /** `in:` values; a section matches when its id or title contains one. */
  in: string[];
}

const NAMES: Status[] = ['unknown', 'not_implemented', 'partial', 'implemented', 'fully_functional', 'not_planned'];

const norm = (s: string) => s.toLowerCase().replace(/[\s_-]+/g, '');

/** `is:fully`, `is:fully_functional`, `is:not-planned`: unambiguous prefixes work. */
export function resolveStatus(word: string): Status | null {
  const w = norm(word);
  if (!w) return null;
  const exact = NAMES.find((n) => norm(n) === w);
  if (exact) return exact;
  const hits = NAMES.filter((n) => norm(n).startsWith(w));
  return hits.length === 1 ? hits[0] : null;
}

export function parseQuery(text: string): Query {
  const q: Query = { terms: [], is: [], notIs: [], in: [] };
  for (const word of text.trim().split(/\s+/).filter(Boolean)) {
    const lower = word.toLowerCase();
    if (lower.startsWith('is:') || lower.startsWith('-is:')) {
      const neg = lower.startsWith('-');
      const status = resolveStatus(word.slice(neg ? 4 : 3));
      if (status) {
        (neg ? q.notIs : q.is).push(status);
        continue;
      }
    } else if (lower.startsWith('in:') && lower.length > 3) {
      q.in.push(lower.slice(3));
      continue;
    }
    q.terms.push(lower);
  }
  return q;
}

export function isEmpty(q: Query): boolean {
  return !q.terms.length && !q.is.length && !q.notIs.length && !q.in.length;
}

export function sectionMatches(q: Query, s: Pick<SectionData, 'id' | 'title'>): boolean {
  if (!q.in.length) return true;
  const hay = `${s.id} ${s.title}`.toLowerCase();
  return q.in.some((v) => hay.includes(v));
}

export function rowMatches(q: Query, r: RowTuple): boolean {
  const [id, group, name, status, note] = r;
  if (q.is.length && !q.is.includes(status)) return false;
  if (q.notIs.includes(status)) return false;
  if (!q.terms.length) return true;
  const hay = `${name} ${id} ${group} ${note} ${status}`.toLowerCase();
  return q.terms.every((t) => hay.includes(t));
}

/** Adds or removes `is:<status>` in a query string (the counter pills use it). */
export function toggleIs(text: string, status: Status): string {
  const token = `is:${status}`;
  const words = text.trim().split(/\s+/).filter(Boolean);
  const has = words.some((w) => w.toLowerCase() === token);
  return (has ? words.filter((w) => w.toLowerCase() !== token) : [...words, token]).join(' ');
}
